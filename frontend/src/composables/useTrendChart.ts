// 趋势折线图（SVG）绘制工具：被数据总览 / 访问分析 / 用户统计三个视图共用。
// 仅提供纯绘制函数，具体数据点由各视图自行计算后传入。
export function useTrendChart() {
  const chartW = 520
  const chartH = 220

  function buildPath(points: number[], max: number): string {
    if (!points.length) return ''
    const stepX = chartW / (points.length - 1 || 1)
    const padY = 20
    const drawH = chartH - padY * 2
    return points.map((v, i) => {
      const x = i * stepX
      const y = chartH - padY - (v / max) * drawH
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
    }).join(' ')
  }

  interface TrendGeom {
    linePath: string
    areaPath: string
    dotCoords: { cx: string; cy: string; val: number }[]
  }

  // 由一串数值 + 最大值生成折线/面积/数据点几何
  function makeTrend(points: number[], max: number): TrendGeom {
    const linePath = buildPath(points, max)
    const areaPath = linePath
      ? `${linePath} L ${chartW.toFixed(1)} ${chartH} L 0 ${chartH} Z`
      : ''
    const stepX = chartW / (points.length - 1 || 1)
    const padY = 20
    const drawH = chartH - padY * 2
    const dotCoords = points.map((v, i) => ({
      cx: (i * stepX).toFixed(1),
      cy: (chartH - padY - (v / max) * drawH).toFixed(1),
      val: v,
    }))
    return { linePath, areaPath, dotCoords }
  }

  return { chartW, chartH, buildPath, makeTrend }
}
