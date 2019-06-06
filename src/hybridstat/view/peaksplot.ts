import {Range1d}       from "models/ranges/range1d"
import {PeaksStatsDiv} from "./peakstats"

on_change_bounds(fig: Plot, src: ColumnDataSource): void {
    this.on_change_bases(fig)
    const yrng = fig.y_range as Range1d
    const zval = src.data["z"] as number[]
    let ix1: number  = 0
    let ix2: number  = zval.length
    for(let i = 0; i <= zval.length; ++i) {
        if (zval[i] <= yrng.start) {
            ix1 = i+1
            continue
        }
        if (zval[i] > yrng.end) {
            ix2 = i
            break
        }
    }

    const dur = fig.extra_x_ranges['duration'] as Range1d
    const cnt = fig.x_range as Range1d

    dur.start = 0
    cnt.start = 0
    if(zval.length < 2 || ix1 == ix2) {
        dur.end = 0
        cnt.end = 0
    } else {
        dur.end = Math.max.apply(Math, (src.data["duration"] as number []).slice(ix1, ix2))*1.05
        cnt.end = Math.max.apply(Math, (src.data["count"] as number[]).slice(ix1, ix2))*1.05
    }
}

on_change_bases(fig:Plot): void {
    const yrng         = fig.y_range as Range1d
    const bases        = fig.extra_y_ranges['bases'] as Range1d
    bases.start        = (yrng.start - this.bias)*this.stretch
    bases.end          = (yrng.end   - this.bias)*this.stretch
    bases.reset_start  = (yrng.reset_start - this.bias)*this.stretch
    bases.reset_end    = (yrng.reset_end   - this.bias)*this.stretch
}

on_change_sequence(
    src:   ColumnDataSource,
    peaks: {source: ColumnDataSource},
    stats: PeaksStatsDiv,
    tick1: {key: string},
    tick2: {key: string},
    menu:  {value: string, menu: [string, string][], label: string}
): void {
    if (Object.keys(src.data).indexOf(menu.value) > -1) {
        let good: boolean = false
        for(let i of menu.menu)
            if ((i != null) && (i[1] == menu.value))
            {
                menu.label = i[0]
                good       = true
                break
            }
        if (!good)
            menu.label = menu.value

        tick1.key        = menu.value
        tick2.key        = menu.value
        src.data['text'] = src.data[menu.value]
        src.change.emit()

        if (stats.data[menu.value] != null)
            stats.text = stats.data[menu.value]

        let emit: boolean = false
        for(let key of ['id', 'bases', 'distance', 'orient', 'color']) {
            const col = peaks.source.data[menu.value+key]
            if (col != null)
            {
                peaks.source.data[key] = col
                emit                   = true
            }
        }
        if (emit)
            peaks.source.change.emit()

        if (Object.keys(this.stretches).indexOf(menu.value) > -1)
        {
            this.updating = 'seq'
            this.stretch  = this.stretches[menu.value]
            this.bias     = this.biases[menu.value]
            this.updating = '*'
            this.updating = ''
        }
    }
}
