from django.db import migrations

CREATION_EVIDENCE_SQL = """
CREATE FUNCTION characters_validate_creation_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM characters_character AS character
        JOIN characters_characterownership AS ownership
          ON ownership.character_id = character.character_id
        JOIN identity_gameaccount AS account
          ON account.game_account_id = ownership.game_account_id
        JOIN content_contentreleasebatch AS batch
          ON batch.batch_id = NEW.content_release_batch_id
        JOIN content_contentreleasehead AS release_head
          ON release_head.release_head_id = batch.release_head_id
        JOIN content_contentreleaseitem AS release_item
          ON release_item.batch_id = batch.batch_id
         AND release_item.release_head_id = release_head.release_head_id
         AND release_item.published_revision_id = NEW.start_room_revision_id
        WHERE character.character_id = NEW.character_id
          AND ownership.game_account_id = NEW.game_account_id
          AND character.instance_id = account.instance_id
          AND release_head.instance_id = account.instance_id
          AND character.start_room_revision_id = NEW.start_room_revision_id
          AND character.normalized_display_name = NEW.normalized_display_name
          AND character.gender = NEW.gender
          AND character.pronouns = NEW.pronouns
          AND character.initial_state = NEW.resolved_initial_state
    ) THEN
        RAISE EXCEPTION 'character creation evidence is inconsistent'
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER characters_creation_evidence_contract_trigger
AFTER INSERT ON characters_charactercreationrecord
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION characters_validate_creation_evidence();
"""


CREATION_EVIDENCE_REVERSE_SQL = """
DROP TRIGGER IF EXISTS characters_creation_evidence_contract_trigger
ON characters_charactercreationrecord;
DROP FUNCTION IF EXISTS characters_validate_creation_evidence();
"""


class Migration(migrations.Migration):
    dependencies = [("characters", "0002_immutable_creation_history")]

    operations = [
        migrations.RunSQL(
            sql=CREATION_EVIDENCE_SQL,
            reverse_sql=CREATION_EVIDENCE_REVERSE_SQL,
        )
    ]
