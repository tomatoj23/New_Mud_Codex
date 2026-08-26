from django.db import migrations

POSTGRES_CONTRACT_SQL = r"""
CREATE FUNCTION identity_check_session_contract()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM identity_authsession session
        JOIN identity_gameaccount account
          ON account.game_account_id = session.game_account_id
        JOIN identity_refreshtokenfamily family
          ON family.family_id = session.refresh_family_id
         AND family.auth_session_id = session.auth_session_id
        WHERE session.auth_session_id = NEW.auth_session_id
          AND account.user_id = session.user_id
          AND family.absolute_expires_at <= session.absolute_expires_at
          AND ((session.state = 'active') = (family.state = 'active'))
    ) THEN
        RAISE EXCEPTION 'AuthSession lifetime identity contract is invalid'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_session_lifetime_contract';
    END IF;
    RETURN NULL;
END;
$$;

CREATE FUNCTION identity_check_family_contract()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM identity_refreshtokenfamily family
        JOIN identity_authsession session
          ON session.auth_session_id = family.auth_session_id
         AND session.refresh_family_id = family.family_id
        JOIN identity_gameaccount account
          ON account.game_account_id = session.game_account_id
        WHERE family.family_id = NEW.family_id
          AND account.user_id = session.user_id
          AND family.absolute_expires_at <= session.absolute_expires_at
          AND ((session.state = 'active') = (family.state = 'active'))
    ) THEN
        RAISE EXCEPTION 'RefreshTokenFamily lifetime identity contract is invalid'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_family_lifetime_contract';
    END IF;
    RETURN NULL;
END;
$$;

CREATE FUNCTION identity_assert_family_credentials(target_family_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM identity_refreshtokenfamily family
        WHERE family.family_id = target_family_id
          AND (
              (
                  SELECT max(credential.generation)
                  FROM identity_refreshtokencredential credential
                  WHERE credential.family_id = family.family_id
              ) IS DISTINCT FROM family.current_generation
              OR EXISTS (
                  SELECT 1
                  FROM identity_refreshtokencredential credential
                  WHERE credential.family_id = family.family_id
                    AND credential.expires_at > family.absolute_expires_at
              )
              OR EXISTS (
                  SELECT 1
                  FROM identity_refreshtokencredential credential
                  JOIN identity_refreshtokencredential successor
                    ON successor.credential_id = credential.replaced_by_id
                  WHERE credential.family_id = family.family_id
                    AND (
                        successor.family_id <> credential.family_id
                        OR successor.generation <> credential.generation + 1
                    )
              )
              OR (
                  family.state = 'active'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM identity_refreshtokencredential credential
                      WHERE credential.family_id = family.family_id
                        AND credential.state = 'active'
                        AND credential.generation = family.current_generation
                  )
              )
              OR (
                  family.state <> 'active'
                  AND EXISTS (
                      SELECT 1
                      FROM identity_refreshtokencredential credential
                      WHERE credential.family_id = family.family_id
                        AND credential.state = 'active'
                  )
              )
          )
    ) THEN
        RAISE EXCEPTION 'RefreshTokenFamily credential contract is invalid'
            USING ERRCODE = '23514', CONSTRAINT = 'identity_family_credential_contract';
    END IF;
END;
$$;

CREATE FUNCTION identity_check_family_credentials()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM identity_assert_family_credentials(NEW.family_id);
    RETURN NULL;
END;
$$;

CREATE FUNCTION identity_check_credential_family()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM identity_assert_family_credentials(COALESCE(NEW.family_id, OLD.family_id));
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER identity_session_contract_trigger
AFTER INSERT OR UPDATE ON identity_authsession
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION identity_check_session_contract();

CREATE CONSTRAINT TRIGGER identity_family_contract_trigger
AFTER INSERT OR UPDATE ON identity_refreshtokenfamily
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION identity_check_family_contract();

CREATE CONSTRAINT TRIGGER identity_family_credentials_trigger
AFTER INSERT OR UPDATE ON identity_refreshtokenfamily
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION identity_check_family_credentials();

CREATE CONSTRAINT TRIGGER identity_credential_family_trigger
AFTER INSERT OR UPDATE OR DELETE ON identity_refreshtokencredential
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION identity_check_credential_family();
"""

POSTGRES_CONTRACT_REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS identity_credential_family_trigger ON identity_refreshtokencredential;
DROP TRIGGER IF EXISTS identity_family_credentials_trigger ON identity_refreshtokenfamily;
DROP TRIGGER IF EXISTS identity_family_contract_trigger ON identity_refreshtokenfamily;
DROP TRIGGER IF EXISTS identity_session_contract_trigger ON identity_authsession;
DROP FUNCTION IF EXISTS identity_check_credential_family();
DROP FUNCTION IF EXISTS identity_check_family_credentials();
DROP FUNCTION IF EXISTS identity_assert_family_credentials(uuid);
DROP FUNCTION IF EXISTS identity_check_family_contract();
DROP FUNCTION IF EXISTS identity_check_session_contract();
"""


class Migration(migrations.Migration):
    dependencies = [("identity", "0001_initial")]

    operations = [
        migrations.RunSQL(POSTGRES_CONTRACT_SQL, POSTGRES_CONTRACT_REVERSE_SQL),
    ]
