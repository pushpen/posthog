# Generated by Django 3.0.3 on 2020-04-03 09:32

import re
from typing import Dict, List, Union

from django.db import connection, migrations, models
from django.db.models import Exists, F, OuterRef, Q, Subquery

attribute_regex = r"([a-zA-Z]*)\[(.*)=[\'|\"](.*)[\'|\"]\]"


def split_selector_into_parts(selector: str):
    tags = selector.split(" > ")
    tags.reverse()
    ret: List[Dict[str, Union[str, List]]] = []
    for tag in tags:
        data: Dict[str, Union[str, List]] = {}
        if "[id=" in tag:
            result = re.search(attribute_regex, tag)
            data["attr_id"] = result[3]  # type: ignore
            tag = result[1]  # type: ignore
        if "[" in tag:
            result = re.search(attribute_regex, tag)
            data[f"attributes__{result[2]}"] = result[3]  # type: ignore
            tag = result[1]  # type: ignore
        if "nth-child(" in tag:
            parts = tag.split(":nth-child(")
            data["nth_child"] = parts[1].replace(")", "")
            tag = parts[0]
        if "." in tag:
            parts = tag.split(".")
            data["attr_class"] = parts[1:]
            tag = parts[0]
        if tag:
            data["tag_name"] = tag
        ret.append(data)
    return ret


# Freeze this version of the eventmanager
class EventManager:
    def filter_by_element(self, action_step, apps):
        ElementGroup = apps.get_model("posthog", "ElementGroup")
        Element = apps.get_model("posthog", "Element")
        groups = ElementGroup.objects.filter(team=action_step.action.team_id)
        filter = {}
        for key in ["tag_name", "text", "href", "name"]:
            if getattr(action_step, key):
                filter[f"element__{key}"] = getattr(action_step, key)

        if action_step.selector:
            parts = split_selector_into_parts(action_step.selector)
            subqueries = {}
            for index, tag in enumerate(parts):
                if tag.get("attr_class"):
                    attr_class = tag.pop("attr_class")
                    tag["attr_class__contains"] = attr_class
                subqueries[f"match_{index}"] = Subquery(
                    Element.objects.filter(group_id=OuterRef("pk"), **tag).values("order")[:1]
                )
            groups = groups.annotate(**subqueries)
            for index, _ in enumerate(parts):
                filter[f"match_{index}__isnull"] = False
                if index > 0:
                    filter[f"match_{index}__gt"] = F(
                        f"match_{index - 1}"
                    )  # make sure the ordering of the elements is correct

        if not filter:
            return {}
        groups = groups.filter(**filter)
        return {"elements_hash__in": groups.values_list("hash", flat=True)}

    def filter_by_url(self, action_step):
        if not action_step.url:
            return {}
        if action_step.url_matching == "exact":
            return {"properties__$current_url": action_step.url}
        return {"properties__$current_url__icontains": action_step.url}

    def filter_by_event(self, action_step):
        if not action_step.event:
            return {}
        return {"event": action_step.event}

    def query_db_by_action(self, events: models.QuerySet, action, apps) -> models.QuerySet:
        any_step = Q()
        for step in action.steps.all():
            any_step |= Q(
                **self.filter_by_element(step, apps), **self.filter_by_url(step), **self.filter_by_event(step)
            )
        events = events.filter(team_id=action.team_id).filter(any_step)

        return events


def migrate_to_precalculate_actions(apps, schema_editor):
    Action = apps.get_model("posthog", "Action")

    Event = apps.get_model("posthog", "Event")

    actions = Action.objects.all()
    manager = EventManager()
    for action in actions:
        print(f"team: {action.team} action: {action.name}")
        try:
            event_query, params = (
                manager.query_db_by_action(Event.objects.all(), action, apps).only("pk").query.sql_with_params()
            )
        except:  # make specific
            action.events.all().delete()
            return

        query = """
        DELETE FROM "posthog_action_events" WHERE "action_id" = {};
        INSERT INTO "posthog_action_events" ("action_id", "event_id")
        {}
        ON CONFLICT DO NOTHING
        """.format(
            action.pk, event_query.replace("SELECT ", f"SELECT {action.pk}, ", 1),
        )

        cursor = connection.cursor()
        cursor.execute(query, params)


def rollback(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("posthog", "0037_action_step_url_matching_can_be_null_20200402_1351"),
    ]

    operations = [
        migrations.AddField(
            model_name="action", name="events", field=models.ManyToManyField(blank=True, to="posthog.Event"),
        ),
        migrations.RunPython(migrate_to_precalculate_actions, rollback),
    ]
