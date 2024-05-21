"""
This is a boilerplate pipeline 'data_processing'
generated using Kedro 0.19.5
"""
def data_processing(itt, itrt):
    trends = (
    itt.filter(itt.score.notnull()).mutate(month=itt.week.cast('string').left(7))
    .group_by([itt.country_name, 'month', itt.term])
    .aggregate(avg_score=itt.score.mean())
    )
    
    rising_trends = (
    itrt.mutate(month=itrt.week.cast('string').left(7))
    .group_by([itrt.country_name, 'month', itrt.term])
    .aggregate(avg_percent_gain=itrt.percent_gain.mean())
    )

    result = trends.left_join(
    rising_trends,
    [
        trends.country_name == rising_trends.country_name,
        trends.month == rising_trends.month,
        trends.term == rising_trends.term
    ]
    )[
        trends.country_name,
        trends.month,
        trends.term.name('google_trend'),
        trends.avg_score,
        rising_trends.avg_percent_gain
    ]

    return result.to_pandas()