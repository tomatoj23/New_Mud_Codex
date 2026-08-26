from django.db import migrations

POSTGRES_IMMUTABILITY_SQL = r"""
CREATE FUNCTION identity_reject_family_identity_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.auth_session_id IS DISTINCT FROM OLD.auth_session_id
       OR NEW.absolute_expires_at IS DISTINCT FROM OLD.absolute_expires_at THEN
        RAISE EXCEPTION 'RefreshTokenFamily lifetime identity fields are immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_family_identity_immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION identity_reject_credential_identity_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.family_id IS DISTINCT FROM OLD.family_id
       OR NEW.generation IS DISTINCT FROM OLD.generation THEN
        RAISE EXCEPTION 'RefreshTokenCredential identity fields are immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_credential_identity_immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION identity_check_refresh_terminal_retention()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    family_expires_at timestamptz;
BEGIN
    SELECT absolute_expires_at
      INTO family_expires_at
      FROM identity_refreshtokenfamily
     WHERE family_id = NEW.family_id;

    IF family_expires_at IS NULL
       OR NEW.expires_at < GREATEST(
           NEW.created_at + INTERVAL '24 hours',
           family_expires_at + INTERVAL '24 hours'
       ) THEN
        RAISE EXCEPTION 'RefreshRequestTerminalRecord retention is too short'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_terminal_retention_floor';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER identity_family_immutable_trigger
BEFORE UPDATE ON identity_refreshtokenfamily
FOR EACH ROW EXECUTE FUNCTION identity_reject_family_identity_change();

CREATE TRIGGER identity_credential_immutable_trigger
BEFORE UPDATE ON identity_refreshtokencredential
FOR EACH ROW EXECUTE FUNCTION identity_reject_credential_identity_change();

CREATE TRIGGER identity_terminal_retention_trigger
BEFORE INSERT OR UPDATE OF family_id, created_at, expires_at
ON identity_refreshrequestterminalrecord
FOR EACH ROW EXECUTE FUNCTION identity_check_refresh_terminal_retention();
"""

POSTGRES_IMMUTABILITY_REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS identity_terminal_retention_trigger
    ON identity_refreshrequestterminalrecord;
DROP TRIGGER IF EXISTS identity_credential_immutable_trigger
    ON identity_refreshtokencredential;
DROP TRIGGER IF EXISTS identity_family_immutable_trigger
    ON identity_refreshtokenfamily;
DROP FUNCTION IF EXISTS identity_check_refresh_terminal_retention();
DROP FUNCTION IF EXISTS identity_reject_credential_identity_change();
DROP FUNCTION IF EXISTS identity_reject_family_identity_change();
"""


class Migration(migrations.Migration):
    dependencies = [("identity", "0002_lifetime_contract_guards")]

    operations = [
        migrations.RunSQL(
            POSTGRES_IMMUTABILITY_SQL,
            POSTGRES_IMMUTABILITY_REVERSE_SQL,
        ),
    ]
