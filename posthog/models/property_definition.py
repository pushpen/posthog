from django.contrib.postgres.indexes import GinIndex
from django.db import models

from posthog.models.team import Team
from posthog.models.utils import UUIDModel


class PropertyType(models.TextChoices):
    Datetime = "DateTime", "DateTime"
    String = "String", "String"
    Numeric = "Numeric", "Numeric"
    Boolean = "Boolean", "Boolean"


class PropertyFormat(models.TextChoices):
    UnixTimestamp = "unix_timestamp", "Unix Timestamp"
    FullDate = "YYYY-MM-DD hh:mm:ss", "YYYY-MM-DD hh:mm:ss"
    Date = "YYYY-MM-DD", "YYYY-MM-DD"


class PropertyDefinition(UUIDModel):
    team: models.ForeignKey = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="property_definitions", related_query_name="team",
    )
    name: models.CharField = models.CharField(max_length=400)
    is_numerical: models.BooleanField = models.BooleanField(
        default=False,
    )  # whether the property can be interpreted as a number, and therefore used for math aggregation operations
    query_usage_30_day: models.IntegerField = models.IntegerField(
        default=None, null=True,
    )  # Number of times the event has been used in a query in the last 30 rolling days (computed asynchronously)

    property_type = models.CharField(max_length=50, choices=PropertyType.choices, blank=True, null=True)

    property_type_format = models.CharField(max_length=50, choices=PropertyFormat.choices, blank=True, null=True)

    # DEPRECATED
    volume_30_day: models.IntegerField = models.IntegerField(
        default=None, null=True,
    )  # Deprecated in #4480

    class Meta:
        unique_together = ("team", "name")
        indexes = [
            GinIndex(name="index_property_definition_name", fields=["name"], opclasses=["gin_trgm_ops"]),
        ]  # To speed up DB-based fuzzy searching
        constraints = [
            models.CheckConstraint(
                name="property_type_and_format_are_valid",
                check=models.Q(
                    (models.Q(property_type__in=PropertyType.values))
                    & (models.Q(property_type_format__in=PropertyFormat.values))
                ),
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} / {self.team.name}"

    # This is a dynamically calculated field in api/property_definition.py. Defaults to `True` here to help serializers.
    def is_event_property(self) -> None:
        return None
