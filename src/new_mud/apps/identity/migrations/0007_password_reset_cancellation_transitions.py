from django.db import migrations

FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION identity_guard_verification_challenge()
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
           (
               OLD.state = 'pending_delivery'
               AND NEW.state IN ('active', 'superseded', 'delivery_failed')
           )
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

CREATE OR REPLACE FUNCTION identity_guard_verification_delivery()
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
           (OLD.state = 'pending' AND NEW.state IN ('leased', 'delivery_failed'))
           OR (OLD.state = 'leased' AND NEW.state IN ('pending', 'delivered', 'delivery_failed'))
       ) THEN
        RAISE EXCEPTION 'VerificationDeliveryOutbox state transition is invalid'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_delivery_transition_valid';
    END IF;
    RETURN NEW;
END;
$$;
"""


REVERSE_SQL = r"""
CREATE OR REPLACE FUNCTION identity_guard_verification_challenge()
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

CREATE OR REPLACE FUNCTION identity_guard_verification_delivery()
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
"""


class Migration(migrations.Migration):
    dependencies = [("identity", "0006_verification_immutability_guards")]

    operations = [migrations.RunSQL(FORWARD_SQL, REVERSE_SQL)]
