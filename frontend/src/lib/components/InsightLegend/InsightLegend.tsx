import './InsightLegend.scss'
import React from 'react'
import { Button, Row, Col } from 'antd'
import { useActions, useValues } from 'kea'
import { IconLegend } from 'lib/components/icons'
import { insightLogic } from 'scenes/insights/insightLogic'
import { trendsLogic } from 'scenes/trends/trendsLogic'
import { InsightLabel } from 'lib/components/InsightLabel'
import { getChartColors } from 'lib/colors'
import { PHCheckbox } from 'lib/components/PHCheckbox'
import { formatCompareLabel } from 'scenes/insights/InsightsTable/InsightsTable'
import { InsightType } from '~/types'
import { FEATURE_FLAGS } from 'lib/constants'
import { featureFlagLogic } from 'lib/logic/featureFlagLogic'

export function InsightLegendButton(): JSX.Element | null {
    const { filters, activeView } = useValues(insightLogic)
    const { toggleInsightLegend } = useActions(insightLogic)
    const { featureFlags } = useValues(featureFlagLogic)

    if (
        !(
            (activeView === InsightType.TRENDS || activeView === InsightType.STICKINESS) &&
            featureFlags[FEATURE_FLAGS.INSIGHT_LEGENDS]
        )
    ) {
        return null
    }

    return (
        <Button className="insight-legend-button" onClick={toggleInsightLegend}>
            <IconLegend />
            <span className="insight-legend-button-title">{filters.legend_hidden ? 'Show' : 'Hide'} legend</span>
        </Button>
    )
}

export function InsightLegend(): JSX.Element {
    const { insightProps, filters } = useValues(insightLogic)
    const logic = trendsLogic(insightProps)
    const { indexedResults, visibilityMap } = useValues(logic)
    const { toggleVisibility } = useActions(logic)
    const colorList = getChartColors('white', indexedResults.length, !!filters.compare)

    return (
        <div className="insight-legend-menu">
            <div className="insight-legend-menu-scroll">
                {indexedResults &&
                    indexedResults.map((item) => {
                        return (
                            <Row key={item.id} className="insight-legend-menu-item" wrap={false}>
                                <Col>
                                    <PHCheckbox
                                        color={colorList[item.id]}
                                        checked={visibilityMap[item.id]}
                                        onChange={() => toggleVisibility(item.id)}
                                    />
                                </Col>
                                <Col>
                                    <InsightLabel
                                        key={item.id}
                                        seriesColor={colorList[item.id]}
                                        action={item.action}
                                        fallbackName={item.breakdown_value === '' ? 'None' : item.label}
                                        hasMultipleSeries={indexedResults.length > 1}
                                        breakdownValue={
                                            item.breakdown_value === '' ? 'None' : item.breakdown_value?.toString()
                                        }
                                        compareValue={filters.compare ? formatCompareLabel(item) : undefined}
                                        hideIcon
                                    />
                                </Col>
                            </Row>
                        )
                    })}
            </div>
        </div>
    )
}
