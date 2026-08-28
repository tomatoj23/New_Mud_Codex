from django.db import migrations

CREATION_REQUEST_SQL = """
CREATE FUNCTION characters_validate_creation_request()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.response_status <> 201
       OR NEW.canonical_request_hash !~ '^[0-9a-f]{64}$'
       OR NEW.idempotency_key !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'
       OR NOT EXISTS (
           SELECT 1
           FROM characters_character AS character
           JOIN characters_characterownership AS ownership
             ON ownership.character_id = character.character_id
           JOIN characters_charactercreationrecord AS evidence
             ON evidence.character_id = character.character_id
            AND evidence.game_account_id = ownership.game_account_id
           WHERE character.character_id = NEW.character_id
             AND ownership.game_account_id = NEW.game_account_id
             AND NEW.response_json ->> 'character_id' = character.character_id::text
             AND NEW.response_json ->> 'display_name' = character.display_name
             AND NEW.response_json ->> 'gender' = character.gender
             AND NEW.response_json ->> 'pronouns' = character.pronouns
             AND NEW.response_json -> 'creation_profile' ->> 'key' = evidence.profile_key
             AND NEW.response_json -> 'creation_profile' ->> 'version' = evidence.profile_version
             AND NEW.response_json -> 'creation_profile' ->> 'definition_hash'
                 = evidence.profile_definition_hash
             AND NEW.response_json -> 'initial_state_summary' -> 'start_room'
                 = evidence.resolved_initial_state -> 'start_room'
             AND NEW.response_json -> 'initial_state_summary' -> 'stats'
                 = evidence.resolved_initial_state -> 'stats'
             AND NEW.response_json -> 'initial_state_summary' -> 'resources'
                 = evidence.resolved_initial_state -> 'resources'
             AND NEW.response_json -> 'initial_state_summary' -> 'skill_grants'
                 = evidence.resolved_initial_state -> 'skill_grants'
             AND NEW.response_json -> 'initial_state_summary' -> 'item_grants'
                 = evidence.resolved_initial_state -> 'item_grants'
       ) THEN
        RAISE EXCEPTION 'character creation request result is inconsistent'
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER characters_creation_request_contract_trigger
AFTER INSERT ON characters_charactercreationrequestrecord
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION characters_validate_creation_request();
"""


CREATION_REQUEST_REVERSE_SQL = """
DROP TRIGGER IF EXISTS characters_creation_request_contract_trigger
ON characters_charactercreationrequestrecord;
DROP FUNCTION IF EXISTS characters_validate_creation_request();
"""


class Migration(migrations.Migration):
    dependencies = [("characters", "0003_creation_evidence_contract")]

    operations = [
        migrations.RunSQL(
            sql=CREATION_REQUEST_SQL,
            reverse_sql=CREATION_REQUEST_REVERSE_SQL,
        )
    ]
