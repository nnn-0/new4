"""
WebAuthn (Biometric Authentication) Service
Handles biometric credential registration, authentication, and attendance
"""

import base64
import json
import os
import uuid
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, Tuple

from webauthn import generate_registration_options, verify_registration_response, generate_authentication_options, verify_authentication_response
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    AttestationConveyancePreference,
    AuthenticatorAttachment,
    ResidentKeyRequirement,
    PublicKeyCredentialDescriptor,
    AuthenticationCredential,
    RegistrationCredential,
    AuthenticatorAttestationResponse,
    AuthenticatorAssertionResponse
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier

from app import db
from models import User, BiometricCredential, Attendance, AttendancePhoto, WebAuthnOperation
import logging
import pytz
from flask import session

# Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')

class WebAuthnService:
    def __init__(self):
        # Get the proper domain from environment
        replit_domain = os.environ.get('REPLIT_DOMAINS', 'localhost')
        if replit_domain != 'localhost':
            self.rp_id = replit_domain.split(',')[0]
            self.origin = f"https://{self.rp_id}"
        else:
            self.rp_id = 'localhost'
            self.origin = "http://localhost:5000"
        
        self.rp_name = "Smart Attendance System"
        
        logging.info(f"WebAuthn configured: rp_id={self.rp_id}, origin={self.origin}")
        
    def _generate_challenge_with_opid(self, user_id: str) -> Tuple[bytes, str]:
        """Generate a secure random challenge with unique operation ID - eliminates user-level pending mechanism"""
        # Store challenges by operation ID instead of user ID - supports concurrent operations
        if 'webauthn_operations' not in session:
            session['webauthn_operations'] = {}
        
        # Generate unique operation ID for this challenge
        op_id = str(uuid.uuid4())
        current_time = datetime.now().timestamp()
        
        # Generate fresh challenge for each operation
        challenge = os.urandom(32)
        session['webauthn_operations'][op_id] = {
            'user_id': str(user_id),
            'challenge': self._bytes_to_base64(challenge),
            'timestamp': current_time
        }
        session.modified = True
        
        # Clean up expired operations (older than 5 minutes)
        self._cleanup_expired_operations()
        
        logging.info(f"Generated new challenge with opId {op_id} for user {user_id}")
        return challenge, op_id
    
    def _get_challenge_by_opid(self, op_id: str) -> Tuple[Optional[bytes], Optional[str]]:
        """Retrieve challenge by operation ID - eliminates user-level conflicts"""
        if 'webauthn_operations' not in session:
            return None, None
        
        operation_data = session['webauthn_operations'].get(op_id)
        if operation_data:
            challenge_b64 = operation_data['challenge']
            user_id = operation_data['user_id']
            return self._base64_to_bytes(challenge_b64), user_id
        return None, None
    
    def _clear_operation(self, op_id: str):
        """Clear operation after successful verification"""
        if 'webauthn_operations' in session and op_id in session['webauthn_operations']:
            del session['webauthn_operations'][op_id]
            session.modified = True
            logging.info(f"Cleared operation {op_id}")
    
    def _cleanup_expired_operations(self):
        """Remove operations older than 5 minutes"""
        if 'webauthn_operations' not in session:
            return
        
        current_time = datetime.now().timestamp()
        expired_ops = []
        
        for op_id, op_data in session['webauthn_operations'].items():
            if current_time - op_data['timestamp'] > 300:  # 5 minutes
                expired_ops.append(op_id)
        
        for op_id in expired_ops:
            del session['webauthn_operations'][op_id]
        
        if expired_ops:
            session.modified = True
            logging.info(f"Cleaned up {len(expired_ops)} expired operations")
    
    def _base64_to_bytes(self, base64_string: str) -> bytes:
        """Convert base64url string to bytes"""
        # Add padding if necessary
        padding = '=' * ((4 - len(base64_string) % 4) % 4)
        return base64.urlsafe_b64decode(base64_string + padding)
    
    def _bytes_to_base64(self, data: bytes) -> str:
        """Convert bytes to base64url string"""
        return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')
    
    def begin_registration(self, user_id: int) -> Dict[str, Any]:
        """Begin biometric registration process"""
        try:
            user = User.query.get(user_id)
            if not user:
                raise ValueError("User not found")
            
            # Check if user already has biometric credentials
            existing_credentials = BiometricCredential.query.filter_by(
                user_id=user_id, 
                is_active=True
            ).all()
            
            exclude_credentials = []
            for cred in existing_credentials:
                exclude_credentials.append(
                    PublicKeyCredentialDescriptor(
                        id=self._base64_to_bytes(cred.credential_id)
                    )
                )
            
            # Generate registration options
            options = generate_registration_options(
                rp_id=self.rp_id,
                rp_name=self.rp_name,
                user_id=str(user_id).encode('utf-8'),
                user_name=user.username,
                user_display_name=user.full_name or user.username,
                exclude_credentials=exclude_credentials,
                authenticator_selection=AuthenticatorSelectionCriteria(
                    authenticator_attachment=AuthenticatorAttachment.PLATFORM,
                    resident_key=ResidentKeyRequirement.PREFERRED,
                    user_verification=UserVerificationRequirement.REQUIRED,
                ),
                attestation=AttestationConveyancePreference.NONE,
                supported_pub_key_algs=[
                    COSEAlgorithmIdentifier.ECDSA_SHA_256,
                    COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
                ],
            )
            
            # Store the challenge from generate_registration_options under an operation ID
            op_id = str(uuid.uuid4())
            current_time = datetime.now().timestamp()
            
            if 'webauthn_operations' not in session:
                session['webauthn_operations'] = {}
            
            session['webauthn_operations'][op_id] = {
                'user_id': str(user_id),
                'challenge': self._bytes_to_base64(options.challenge),
                'timestamp': current_time
            }
            session.modified = True
            
            # Clean up expired operations
            self._cleanup_expired_operations()
            
            # Convert to JSON-serializable format with operation ID
            return {
                'challenge': self._bytes_to_base64(options.challenge),
                'opId': op_id,  # Send operation ID to client
                'rp': {'id': options.rp.id, 'name': options.rp.name},
                'user': {
                    'id': self._bytes_to_base64(options.user.id),
                    'name': options.user.name,
                    'displayName': options.user.display_name,
                },
                'pubKeyCredParams': [{'alg': param.alg, 'type': param.type} for param in options.pub_key_cred_params],
                'timeout': 120000,  # Increased for scalability
                'excludeCredentials': [
                    {
                        'id': self._bytes_to_base64(cred.id),
                        'type': cred.type,
                        'transports': list(cred.transports) if cred.transports and hasattr(cred, 'transports') else ['internal'],
                    }
                    for cred in (options.exclude_credentials or [])
                ],
                'authenticatorSelection': {
                    'authenticatorAttachment': options.authenticator_selection.authenticator_attachment if options.authenticator_selection else 'platform',
                    'residentKey': options.authenticator_selection.resident_key if options.authenticator_selection else 'preferred',
                    'userVerification': options.authenticator_selection.user_verification if options.authenticator_selection else 'required',
                },
                'attestation': options.attestation,
            }
            
        except Exception as e:
            logging.error(f"WebAuthn registration begin failed: {e}")
            raise
    
    def complete_registration(self, user_id: int, credential_data: Dict[str, Any], op_id: str) -> bool:
        """Complete biometric registration process with operation ID"""
        try:
            user = User.query.get(user_id)
            if not user:
                raise ValueError("User not found")
            
            # Get stored challenge by operation ID - eliminates user-level conflicts
            challenge, challenge_user_id = self._get_challenge_by_opid(op_id)
            if not challenge or challenge_user_id != str(user_id):
                raise ValueError("Invalid or expired operation")
            
            # Create RegistrationCredential object with proper response object
            credential = RegistrationCredential(
                id=credential_data['id'],
                raw_id=self._base64_to_bytes(credential_data['rawId']),
                response=AuthenticatorAttestationResponse(
                    attestation_object=self._base64_to_bytes(credential_data['response']['attestationObject']),
                    client_data_json=self._base64_to_bytes(credential_data['response']['clientDataJSON'])
                ),
                type=credential_data['type']
            )
            
            # Verify registration
            verification = verify_registration_response(
                credential=credential,
                expected_challenge=challenge,
                expected_origin=self.origin,
                expected_rp_id=self.rp_id,
            )
            
            if not verification:
                raise ValueError("Registration verification failed")
            
            # Store credential in database only after successful verification
            biometric_credential = BiometricCredential()
            biometric_credential.user_id = user_id
            biometric_credential.credential_id = self._bytes_to_base64(verification.credential_id)
            biometric_credential.public_key = self._bytes_to_base64(verification.credential_public_key)
            biometric_credential.sign_count = verification.sign_count
            biometric_credential.device_type = 'platform'
            biometric_credential.aaguid = str(verification.aaguid) if verification.aaguid else None
            biometric_credential.is_active = True
            
            db.session.add(biometric_credential)
            db.session.commit()
            
            # Clear operation after successful registration
            self._clear_operation(op_id)
            
            logging.info(f"Biometric credential registered for user {user.username}")
            return True
            
        except Exception as e:
            logging.error(f"WebAuthn registration complete failed: {e}")
            db.session.rollback()
            raise
    
    def begin_authentication(self, username: Optional[str] = None) -> Dict[str, Any]:
        """Begin biometric authentication process using server-side storage"""
        try:
            allow_credentials = []
            user_id = None
            
            if username:
                # User-specific authentication
                user = User.query.filter_by(username=username).first()
                if user:
                    user_id = user.id
                    credentials = BiometricCredential.query.filter_by(
                        user_id=user.id, 
                        is_active=True
                    ).all()
                    
                    if not credentials:
                        raise ValueError("No biometric credentials found for this user")
                    
                    for cred in credentials:
                        allow_credentials.append(
                            PublicKeyCredentialDescriptor(
                                id=self._base64_to_bytes(cred.credential_id)
                            )
                        )
                else:
                    raise ValueError("User not found")
            else:
                # Usernameless authentication - use discoverable credentials
                allow_credentials = None
            
            # Generate authentication options
            options = generate_authentication_options(
                rp_id=self.rp_id,
                allow_credentials=allow_credentials,
                user_verification=UserVerificationRequirement.REQUIRED,
                timeout=300000,
            )
            
            # Store operation in database (not session!)
            op_id = str(uuid.uuid4())
            operation = WebAuthnOperation(
                op_id=op_id,
                user_id=user_id,
                challenge=self._bytes_to_base64(options.challenge)
            )
            db.session.add(operation)
            db.session.commit()
            
            # Clean up old operations (older than 5 minutes)
            cutoff_time = datetime.now() - timedelta(minutes=5)
            WebAuthnOperation.query.filter(WebAuthnOperation.issued_at < cutoff_time).delete()
            db.session.commit()
            
            logging.info(f"Generated authentication options with opId: {op_id} for user {user_id}")
            
            # Convert to JSON-serializable format with operation ID
            return {
                'challenge': self._bytes_to_base64(options.challenge),
                'opId': op_id,
                'timeout': 300000,
                'rpId': options.rp_id,
                'allowCredentials': [
                    {
                        'id': self._bytes_to_base64(cred.id),
                        'type': cred.type,
                        'transports': list(cred.transports) if cred.transports and hasattr(cred, 'transports') else ['internal'],
                    }
                    for cred in (options.allow_credentials or [])
                ],
                'userVerification': options.user_verification,
            }
            
        except Exception as e:
            logging.error(f"WebAuthn authentication begin failed: {e}")
            raise
    
    def complete_authentication(self, credential_data: Dict[str, Any], op_id: str) -> Tuple[bool, Optional[User]]:
        """Complete biometric authentication process using server-side storage"""
        try:
            logging.info(f"Attempting to complete authentication with opId: {op_id}")
            
            # Get operation from database
            operation = WebAuthnOperation.query.filter_by(op_id=op_id).first()
            if not operation:
                logging.error(f"Operation {op_id} not found in database")
                raise ValueError("Invalid or expired operation")
            
            challenge = self._base64_to_bytes(operation.challenge)
            
            # Find credential in database using the base64 encoded ID 
            credential_id_base64 = credential_data['id']
            biometric_cred = BiometricCredential.query.filter_by(
                credential_id=credential_id_base64,
                is_active=True
            ).first()
            
            if not biometric_cred:
                raise ValueError("Credential not found")
            
            user = biometric_cred.user
            
            # Verify user matches operation
            if operation.user_id and operation.user_id != user.id:
                logging.error(f"User mismatch: operation for user {operation.user_id}, credential belongs to user {user.id}")
                raise ValueError("User mismatch")
            
            # Create AuthenticationCredential object with proper response object
            credential = AuthenticationCredential(
                id=credential_data['id'],
                raw_id=self._base64_to_bytes(credential_data['rawId']),
                response=AuthenticatorAssertionResponse(
                    authenticator_data=self._base64_to_bytes(credential_data['response']['authenticatorData']),
                    client_data_json=self._base64_to_bytes(credential_data['response']['clientDataJSON']),
                    signature=self._base64_to_bytes(credential_data['response']['signature'])
                ),
                type=credential_data['type']
            )
            
            # Verify authentication
            verification = verify_authentication_response(
                credential=credential,
                expected_challenge=challenge,
                expected_origin=self.origin,
                expected_rp_id=self.rp_id,
                credential_public_key=self._base64_to_bytes(biometric_cred.public_key),
                credential_current_sign_count=biometric_cred.sign_count,
            )
            
            if not verification:
                raise ValueError("Authentication verification failed")
            
            # Update sign count
            biometric_cred.sign_count = verification.new_sign_count
            biometric_cred.last_used = datetime.now()
            
            # Delete operation after successful verification
            db.session.delete(operation)
            db.session.commit()
            
            logging.info(f"Biometric authentication successful for user {user.username}")
            return True, user
            
        except Exception as e:
            logging.error(f"WebAuthn authentication complete failed: {e}")
            return False, None
    
    def mark_attendance_with_biometric(self, user_id: int, credential_data: Dict[str, Any], photo_data: str, op_id: str) -> Tuple[bool, str]:
        """Mark attendance using biometric verification and photo"""
        try:
            # Verify biometric authentication
            verified, user = self.complete_authentication(credential_data, op_id)
            
            if not verified or not user or user.id != user_id:
                raise ValueError("Biometric verification failed")
            
            # Check attendance time windows
            now_ist = datetime.now(IST)
            today = now_ist.date()
            current_time = now_ist.time()
            
            from routes import MORNING_START_TIME, MORNING_END_TIME, EVENING_START_TIME, EVENING_END_TIME, get_current_session
            
            current_session = get_current_session()
            if not current_session:
                raise ValueError("Attendance can only be marked during allowed time windows")
            
            # Check if attendance already marked for this session
            existing_attendance = Attendance.query.filter_by(
                user_id=user_id,
                date=today,
                session=current_session
            ).first()
            
            if existing_attendance:
                raise ValueError(f"Attendance already marked for {current_session} session")
            
            # Save photo
            photo_filename = f"attendance_{user_id}_{today}_{current_session}_{now_ist.strftime('%H%M%S')}.jpg"
            photo_path = os.path.join('static', 'attendance_photos', photo_filename)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(photo_path), exist_ok=True)
            
            # Save base64 photo data
            if photo_data.startswith('data:image'):
                photo_data = photo_data.split(',')[1]
            
            with open(photo_path, 'wb') as f:
                f.write(base64.b64decode(photo_data))
            
            # Create attendance record
            attendance = Attendance()
            attendance.user_id = user_id
            attendance.date = today
            attendance.session = current_session
            attendance.status = 'present'
            attendance.biometric_confidence = 100.0  # Biometric is 100% confident
            
            db.session.add(attendance)
            db.session.flush()  # Get attendance ID
            
            # Create photo record
            attendance_photo = AttendancePhoto()
            attendance_photo.attendance_id = attendance.id
            attendance_photo.photo_filename = photo_filename
            attendance_photo.verification_method = 'biometric'
            
            db.session.add(attendance_photo)
            db.session.commit()
            
            logging.info(f"Biometric attendance marked for user {user.username} - {current_session} session")
            return True, current_session
            
        except Exception as e:
            logging.error(f"Biometric attendance marking failed: {e}")
            db.session.rollback()
            raise

# Create global service instance
webauthn_service = WebAuthnService()