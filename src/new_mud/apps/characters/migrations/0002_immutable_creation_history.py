from django.db import migrations

IMMUTABILITY_SQL = """
CREATE FUNCTION characters_reject_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME USING ERRCODE = '23514';
END;
$$;

CREATE TRIGGER characters_creation_record_immutable_trigger
BEFORE UPDATE OR DELETE ON characters_charactercreationrecord
FOR EACH ROW EXECUTE FUNCTION characters_reject_immutable_mutation();

CREATE TRIGGER characters_creation_request_immutable_trigger
BEFORE UPDATE OR DELETE ON characters_charactercreationrequestrecord
FOR EACH ROW EXECUTE FUNCTION characters_reject_immutable_mutation();

CREATE TRIGGER characters_ownership_immutable_trigger
BEFORE UPDATE OR DELETE ON characters_characterownership
FOR EACH ROW EXECUTE FUNCTION characters_reject_immutable_mutation();
"""


IMMUTABILITY_REVERSE_SQL = """
DROP TRIGGER IF EXISTS characters_ownership_immutable_trigger
ON characters_characterownership;
DROP TRIGGER IF EXISTS characters_creation_request_immutable_trigger
ON characters_charactercreationrequestrecord;
DROP TRIGGER IF EXISTS characters_creation_record_immutable_trigger
ON characters_charactercreationrecord;
DROP FUNCTION IF EXISTS characters_reject_immutable_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [("characters", "0001_initial")]

    operations = [
        migrations.RunSQL(
            sql=IMMUTABILITY_SQL,
            reverse_sql=IMMUTABILITY_REVERSE_SQL,
        )
    ]
