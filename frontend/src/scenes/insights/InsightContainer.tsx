import { Card, Col, Row } from 'antd'
import { InsightDisplayConfig } from 'scenes/insights/InsightTabs/InsightDisplayConfig'
import { FunnelCanvasLabel } from 'scenes/funnels/FunnelCanvasLabel'
import { ComputationTimeWithRefresh } from 'scenes/insights/ComputationTimeWithRefresh'
import { FunnelVizType, InsightType, ItemMode } from '~/types'
import { TrendInsight } from 'scenes/trends/Trends'
import { FunnelInsight } from 'scenes/insights/FunnelInsight'
import { RetentionContainer } from 'scenes/retention/RetentionContainer'
import { Paths } from 'scenes/paths/Paths'
import { ACTIONS_BAR_CHART_VALUE, ACTIONS_TABLE, FEATURE_FLAGS, FUNNEL_VIZ, FunnelLayout } from 'lib/constants'
import { People } from 'scenes/funnels/FunnelPeople'
import { FunnelStepTable } from 'scenes/insights/InsightTabs/FunnelTab/FunnelStepTable'
import { BindLogic, useValues } from 'kea'
import { trendsLogic } from 'scenes/trends/trendsLogic'
import { InsightsTable } from 'scenes/insights/InsightsTable'
import React from 'react'
import { insightLogic } from 'scenes/insights/insightLogic'
import {
    FunnelInvalidExclusionState,
    FunnelSingleStepState,
    InsightEmptyState,
    InsightErrorState,
    InsightTimeoutState,
} from 'scenes/insights/EmptyStates'
import { Loading } from 'lib/utils'
import { funnelLogic } from 'scenes/funnels/funnelLogic'
import { preflightLogic } from 'scenes/PreflightCheck/logic'
import clsx from 'clsx'
import { featureFlagLogic } from 'lib/logic/featureFlagLogic'
import { PathCanvasLabel } from 'scenes/paths/PathsLabel'
import { FunnelCorrelation } from './FunnelCorrelation'
import { InsightLegend, InsightLegendButton } from 'lib/components/InsightLegend/InsightLegend'

const VIEW_MAP = {
    [`${InsightType.TRENDS}`]: <TrendInsight view={InsightType.TRENDS} />,
    [`${InsightType.STICKINESS}`]: <TrendInsight view={InsightType.STICKINESS} />,
    [`${InsightType.LIFECYCLE}`]: <TrendInsight view={InsightType.LIFECYCLE} />,
    [`${InsightType.SESSIONS}`]: <TrendInsight view={InsightType.SESSIONS} />,
    [`${InsightType.FUNNELS}`]: <FunnelInsight />,
    [`${InsightType.RETENTION}`]: <RetentionContainer />,
    [`${InsightType.PATHS}`]: <Paths />,
}

export function InsightContainer({ disableTable }: { disableTable?: boolean } = { disableTable: false }): JSX.Element {
    const { preflight } = useValues(preflightLogic)
    const { featureFlags } = useValues(featureFlagLogic)
    const {
        insightProps,
        lastRefresh,
        isLoading,
        activeView,
        loadedView,
        filters,
        insightMode,
        showTimeoutMessage,
        showErrorMessage,
    } = useValues(insightLogic)
    const { areFiltersValid, isValidFunnel, areExclusionFiltersValid, correlationAnalysisAvailable } = useValues(
        funnelLogic(insightProps)
    )

    // Empty states that completely replace the graph
    const BlockingEmptyState = (() => {
        if (activeView !== loadedView || isLoading) {
            return (
                <>
                    <div style={{ minHeight: 'min(calc(90vh - 16rem), 36rem)' }} />
                    <Loading />
                </>
            )
        }
        // Insight specific empty states - note order is important here
        if (loadedView === InsightType.FUNNELS) {
            if (!areFiltersValid) {
                return <FunnelSingleStepState />
            }
            if (!areExclusionFiltersValid) {
                return <FunnelInvalidExclusionState />
            }
            if (!isValidFunnel && !isLoading) {
                return <InsightEmptyState />
            }
        }

        // Insight agnostic empty states
        if (showErrorMessage) {
            return <InsightErrorState />
        }
        if (showTimeoutMessage) {
            return <InsightTimeoutState isLoading={isLoading} />
        }

        return null
    })()

    function renderTable(): JSX.Element | null {
        if (
            !preflight?.is_clickhouse_enabled &&
            !showErrorMessage &&
            !showTimeoutMessage &&
            areFiltersValid &&
            activeView === InsightType.FUNNELS &&
            filters?.display === FUNNEL_VIZ
        ) {
            return <People />
        }

        if (
            preflight?.is_clickhouse_enabled &&
            activeView === InsightType.FUNNELS &&
            !showErrorMessage &&
            !showTimeoutMessage &&
            areFiltersValid &&
            filters.funnel_viz_type === FunnelVizType.Steps &&
            filters?.layout === FunnelLayout.horizontal &&
            !disableTable
        ) {
            return <FunnelStepTable />
        }
        if (
            (!filters.display ||
                (filters?.display !== ACTIONS_TABLE && filters?.display !== ACTIONS_BAR_CHART_VALUE)) &&
            (activeView === InsightType.TRENDS || activeView === InsightType.SESSIONS) &&
            !disableTable
        ) {
            /* InsightsTable is loaded for all trend views (except below), plus the sessions view.
    Exclusions:
        1. Table view. Because table is already loaded anyways in `Trends.tsx` as the main component.
        2. Bar value chart. Because this view displays data in completely different dimensions.
    */
            return (
                <BindLogic logic={trendsLogic} props={insightProps}>
                    <InsightsTable
                        showTotalCount={activeView !== InsightType.SESSIONS}
                        filterKey={activeView === InsightType.TRENDS ? `trends_${activeView}` : ''}
                        canEditSeriesNameInline={activeView === InsightType.TRENDS && insightMode === ItemMode.Edit}
                    />
                </BindLogic>
            )
        }

        return null
    }

    return (
        <>
            {/* These are filters that are reused between insight features. They each have generic logic that updates the url */}
            <Card
                title={
                    <InsightDisplayConfig
                        activeView={activeView as InsightType}
                        insightMode={insightMode}
                        filters={filters}
                        disableTable={!!disableTable}
                    />
                }
                data-attr="insights-graph"
                className="insights-graph-container"
            >
                <div>
                    <Row
                        className={clsx('insights-graph-header', {
                            funnels: activeView === InsightType.FUNNELS,
                        })}
                        align="middle"
                        justify="space-between"
                    >
                        {/*Don't add more than two columns in this row.*/}
                        <Col>{lastRefresh && <ComputationTimeWithRefresh />}</Col>
                        <Col>
                            <FunnelCanvasLabel />
                            <PathCanvasLabel />
                            <InsightLegendButton />
                        </Col>
                    </Row>
                    {!!BlockingEmptyState ? (
                        BlockingEmptyState
                    ) : featureFlags[FEATURE_FLAGS.INSIGHT_LEGENDS] &&
                      (activeView === InsightType.TRENDS || activeView === InsightType.STICKINESS) &&
                      !filters.legend_hidden ? (
                        <Row className="insights-graph-container-row" wrap={false}>
                            <Col className="insights-graph-container-row-left">{VIEW_MAP[activeView]}</Col>
                            <Col className="insights-graph-container-row-right">
                                <InsightLegend />
                            </Col>
                        </Row>
                    ) : (
                        VIEW_MAP[activeView]
                    )}
                </div>
            </Card>
            {renderTable()}
            {!disableTable && correlationAnalysisAvailable && activeView === InsightType.FUNNELS && (
                <FunnelCorrelation />
            )}
        </>
    )
}
