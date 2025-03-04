from typing import Counter, List, Set, Union, cast

from ee.clickhouse.materialized_columns.columns import ColumnName, get_materialized_columns
from ee.clickhouse.models.action import get_action_tables_and_properties, uses_elements_chain
from ee.clickhouse.models.property import box_value, extract_tables_and_properties
from posthog.constants import TREND_FILTER_TYPE_ACTIONS, FunnelCorrelationType
from posthog.models.entity import Entity
from posthog.models.filters import Filter
from posthog.models.filters.mixins.utils import cached_property
from posthog.models.filters.path_filter import PathFilter
from posthog.models.filters.retention_filter import RetentionFilter
from posthog.models.filters.stickiness_filter import StickinessFilter
from posthog.models.filters.utils import GroupTypeIndex
from posthog.models.property import PropertyIdentifier, PropertyType, TableWithProperties


class ColumnOptimizer:
    """
    This class is responsible for figuring out what columns can and should be materialized based on the query filter.

    This speeds up queries since clickhouse ends up selecting less data.
    """

    def __init__(self, filter: Union[Filter, PathFilter, RetentionFilter, StickinessFilter], team_id: int):
        self.filter = filter
        self.team_id = team_id

    @cached_property
    def event_columns_to_query(self) -> Set[ColumnName]:
        "Returns a list of event table columns containing materialized properties that this query needs"

        return self.columns_to_query("events", set(self._used_properties_with_type("event")))

    @cached_property
    def person_columns_to_query(self) -> Set[ColumnName]:
        "Returns a list of person table columns containing materialized properties that this query needs"

        return self.columns_to_query("person", set(self._used_properties_with_type("person")))

    def columns_to_query(self, table: TableWithProperties, used_properties: Set[PropertyIdentifier]) -> Set[ColumnName]:
        "Transforms a list of property names to what columns are needed for that query"

        materialized_columns = get_materialized_columns(table)
        return set(materialized_columns.get(property_name, "properties") for property_name, _, _ in used_properties)

    @cached_property
    def is_using_person_properties(self) -> bool:
        return len(self._used_properties_with_type("person")) > 0

    @cached_property
    def group_types_to_query(self) -> Set[GroupTypeIndex]:
        used_properties = self._used_properties_with_type("group")
        return set(cast(GroupTypeIndex, group_type_index) for _, _, group_type_index in used_properties)

    @cached_property
    def should_query_elements_chain_column(self) -> bool:
        "Returns whether this query uses elements_chain"
        has_element_type_property = lambda properties: any(prop.type == "element" for prop in properties)

        if has_element_type_property(self.filter.properties):
            return True

        # Both entities and funnel exclusions can contain nested elements_chain inclusions
        for entity in self.filter.entities + cast(List[Entity], self.filter.exclusions):
            if has_element_type_property(entity.properties):
                return True

            # :TRICKY: Action definition may contain elements_chain usage
            #
            # See ee/clickhouse/models/action.py#format_action_filter for an example
            if entity.type == TREND_FILTER_TYPE_ACTIONS:
                if uses_elements_chain(entity.get_action()):
                    return True

        return False

    @cached_property
    def properties_used_in_filter(self) -> Counter[PropertyIdentifier]:
        "Returns collection of properties + types that this query would use"
        counter: Counter[PropertyIdentifier] = extract_tables_and_properties(self.filter.properties)

        if not isinstance(self.filter, StickinessFilter):
            # Some breakdown types read properties
            #
            # See ee/clickhouse/queries/trends/breakdown.py#get_query or
            # ee/clickhouse/queries/breakdown_props.py#get_breakdown_prop_values
            if self.filter.breakdown_type in ["event", "person"]:
                boxed_breakdown = box_value(self.filter.breakdown)
                for b in boxed_breakdown:
                    if isinstance(b, str):
                        counter[(b, self.filter.breakdown_type, self.filter.breakdown_group_type_index)] += 1
            elif self.filter.breakdown_type == "group":
                # :TRICKY: We only support string breakdown for group properties
                assert isinstance(self.filter.breakdown, str)
                counter[
                    (self.filter.breakdown, self.filter.breakdown_type, self.filter.breakdown_group_type_index)
                ] += 1

            # If we have a breakdowns attribute then make sure we pull in everything we
            # need to calculate it
            for breakdown in self.filter.breakdowns or []:
                counter[(breakdown["property"], breakdown["type"], self.filter.breakdown_group_type_index)] += 1

        # Both entities and funnel exclusions can contain nested property filters
        for entity in self.filter.entities + cast(List[Entity], self.filter.exclusions):
            counter += extract_tables_and_properties(entity.properties)

            # Math properties are also implicitly used.
            #
            # See ee/clickhouse/queries/trends/util.py#process_math
            if entity.math_property:
                counter[(entity.math_property, "event", None)] += 1

            # If groups are involved, they're also used
            #
            # See ee/clickhouse/queries/trends/util.py#process_math
            if entity.math == "unique_group":
                counter[(f"$group_{entity.math_group_type_index}", "event", None)] += 1

            # :TRICKY: If action contains property filters, these need to be included
            #
            # See ee/clickhouse/models/action.py#format_action_filter for an example
            if entity.type == TREND_FILTER_TYPE_ACTIONS:
                counter += get_action_tables_and_properties(entity.get_action())

        if (
            not isinstance(self.filter, StickinessFilter)
            and self.filter.correlation_type == FunnelCorrelationType.PROPERTIES
            and self.filter.correlation_property_names
        ):

            if self.filter.aggregation_group_type_index is not None:
                for prop_value in self.filter.correlation_property_names:
                    counter[(prop_value, "group", self.filter.aggregation_group_type_index)] += 1
            else:
                for prop_value in self.filter.correlation_property_names:
                    counter[(prop_value, "person", None)] += 1

        return counter

    def _used_properties_with_type(self, property_type: PropertyType) -> Counter[PropertyIdentifier]:
        return Counter(
            {
                (name, type, group_type_index): count
                for (name, type, group_type_index), count in self.properties_used_in_filter.items()
                if type == property_type
            }
        )
