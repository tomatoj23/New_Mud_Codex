from django.db import migrations

POSTGRES_VERIFICATION_GUARDS_SQL = r"""
CREATE FUNCTION identity_guard_verification_challenge()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.purpose IS DISTINCT FROM OLD.purpose
       OR NEW.channel IS DISTINCT FROM OLD.channel
       OR NEW.destination_lookup_digest IS DISTINCT FROM OLD.destination_lookup_digest
       OR NEW.destination_lookup_key_id IS DISTINCT FROM OLD.destination_lookup_key_id
       OR NEW.user_id IS DISTINCT FROM OLD.user_id
       OR NEW.code_digest IS DISTINCT FROM OLD.code_digest
       OR NEW.pepper_key_id IS DISTINCT FROM OLD.pepper_key_id
       OR NEW.issued_at IS DISTINCT FROM OLD.issued_at THEN
        RAISE EXCEPTION 'VerificationChallenge identity is immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_challenge_identity_immutable';
    END IF;
    IF OLD.state IN ('consumed', 'superseded', 'expired', 'locked', 'delivery_failed')
       AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'terminal VerificationChallenge is immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_challenge_terminal_immutable';
    END IF;
    IF NEW.state IS DISTINCT FROM OLD.state
       AND NOT (
           (OLD.state = 'pending_delivery' AND NEW.state IN ('active', 'delivery_failed'))
           OR (
               OLD.state = 'active'
               AND NEW.state IN ('consumed', 'superseded', 'expired', 'locked')
           )
       ) THEN
        RAISE EXCEPTION 'VerificationChallenge state transition is invalid'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_challenge_transition_valid';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION identity_guard_verification_delivery()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.challenge_id IS DISTINCT FROM OLD.challenge_id
       OR NEW.template_key IS DISTINCT FROM OLD.template_key
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'VerificationDeliveryOutbox identity is immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_delivery_identity_immutable';
    END IF;
    IF OLD.state IN ('delivered', 'delivery_failed') AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'terminal VerificationDeliveryOutbox is immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_delivery_terminal_immutable';
    END IF;
    IF NEW.state IS DISTINCT FROM OLD.state
       AND NOT (
           (OLD.state = 'pending' AND NEW.state = 'leased')
           OR (OLD.state = 'leased' AND NEW.state IN ('pending', 'delivered', 'delivery_failed'))
       ) THEN
        RAISE EXCEPTION 'VerificationDeliveryOutbox state transition is invalid'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_delivery_transition_valid';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION identity_reject_verification_request_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'VerificationRequestRecord is immutable'
        USING ERRCODE = '23514', CONSTRAINT = 'identity_verification_request_immutable';
END;
$$;

CREATE FUNCTION identity_guard_verified_contact()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.user_id IS DISTINCT FROM OLD.user_id
       OR NEW.channel IS DISTINCT FROM OLD.channel
       OR NEW.lookup_digest IS DISTINCT FROM OLD.lookup_digest
       OR NEW.lookup_key_id IS DISTINCT FROM OLD.lookup_key_id
       OR NEW.verified_at IS DISTINCT FROM OLD.verified_at
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'VerifiedContactMethod identity is immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_contact_identity_immutable';
    END IF;
    IF OLD.state = 'revoked' AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'revoked VerifiedContactMethod is immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_contact_terminal_immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION identity_guard_verification_limit_bucket()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.namespace IS DISTINCT FROM OLD.namespace
       OR NEW.scope IS DISTINCT FROM OLD.scope
       OR NEW.subject_digest IS DISTINCT FROM OLD.subject_digest
       OR NEW.window_seconds IS DISTINCT FROM OLD.window_seconds THEN
        RAISE EXCEPTION 'VerificationRateLimitBucket identity is immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_verification_limit_identity_immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER identity_verification_challenge_guard_trigger
BEFORE UPDATE ON identity_verificationchallenge
FOR EACH ROW EXECUTE FUNCTION identity_guard_verification_challenge();

CREATE TRIGGER identity_verification_delivery_guard_trigger
BEFORE UPDATE ON identity_verificationdeliveryoutbox
FOR EACH ROW EXECUTE FUNCTION identity_guard_verification_delivery();

CREATE TRIGGER identity_verification_request_guard_trigger
BEFORE UPDATE ON identity_verificationrequestrecord
FOR EACH ROW EXECUTE FUNCTION identity_reject_verification_request_update();

CREATE TRIGGER identity_verified_contact_guard_trigger
BEFORE UPDATE ON identity_verifiedcontactmethod
FOR EACH ROW EXECUTE FUNCTION identity_guard_verified_contact();

CREATE TRIGGER identity_verification_limit_guard_trigger
BEFORE UPDATE ON identity_verificationratelimitbucket
FOR EACH ROW EXECUTE FUNCTION identity_guard_verification_limit_bucket();
"""

POSTGRES_VERIFICATION_GUARDS_REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS identity_verification_limit_guard_trigger
    ON identity_verificationratelimitbucket;
DROP TRIGGER IF EXISTS identity_verified_contact_guard_trigger
    ON identity_verifiedcontactmethod;
DROP TRIGGER IF EXISTS identity_verification_request_guard_trigger
    ON identity_verificationrequestrecord;
DROP TRIGGER IF EXISTS identity_verification_delivery_guard_trigger
    ON identity_verificationdeliveryoutbox;
DROP TRIGGER IF EXISTS identity_verification_challenge_guard_trigger
    ON identity_verificationchallenge;
DROP FUNCTION IF EXISTS identity_guard_verification_limit_bucket();
DROP FUNCTION IF EXISTS identity_guard_verified_contact();
DROP FUNCTION IF EXISTS identity_reject_verification_request_update();
DROP FUNCTION IF EXISTS identity_guard_verification_delivery();
DROP FUNCTION IF EXISTS identity_guard_verification_challenge();
"""


class Migration(migrations.Migration):
    dependencies = [("identity", "0005_verification_lifecycle_constraints")]

    operations = [
        migrations.RunSQL(
            POSTGRES_VERIFICATION_GUARDS_SQL,
            POSTGRES_VERIFICATION_GUARDS_REVERSE_SQL,
        )
    ]
