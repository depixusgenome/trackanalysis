import {GlyphRenderer}  from "models/renderers/glyph_renderer"
import {Range1d}        from "models/ranges/range1d"

set_hover(
    rawsrc:ColumnDataSource,
    hvrsrc:ColumnDataSource,
    glyph:GlyphRenderer,
    inds: number[],
    value: number
): void {
    if(this._hvr_cnt != value)
        return

    inds.sort(function (a,b) { return a - b} )
    let ind = inds[Math.floor(inds.length*0.5)]
    ind = Math.floor(ind/this.shape[1]) * this.shape[1]
    if(ind == this.cycle)
        return

    this.cycle       = ind
    hvrsrc.data['z'] = (rawsrc.data['z'] as number[]).slice(ind, ind+this.shape[1])
    glyph.visible    = true
    hvrsrc.change.emit()
}

launch_hover(
    rawsrc:ColumnDataSource,
    hvrsrc:ColumnDataSource,
    glyph:GlyphRenderer,
): void {
    if(this.shape[1] == 2)
        return
    if(rawsrc.selected == null)
        return

    this._hvr_cnt = this._hvr_cnt != null ? this._hvr_cnt + 1 : 0
    let inds      = rawsrc.selected.indices
    if(inds == null || inds.length == 0)
    {
        if(glyph.visible)
        {
            glyph.visible = false
            glyph.change.emit()
        }
        return
    }

    this.set_hover(rawsrc, hvrsrc, glyph, inds, this._hvr_cnt)
}

on_change_hist_bounds(fig:Plot, src: ColumnDataSource): void {
    if(fig.y_range == null)
        return

    if(fig.extra_x_ranges == null)
        return

    const cycles = fig.extra_x_ranges['cycles']
    const frames = fig.x_range

    cycles.start = 0
    frames.start = 0

    const yrng   = fig.y_range as Range1d
    const bases  = fig.extra_y_ranges['bases'] as Range1d
    bases.start  = (yrng.start - this.bias)*this.stretch
    bases.end    = (yrng.end   - this.bias)*this.stretch
    bases.reset_start  = (yrng.reset_start - this.bias)*this.stretch
    bases.reset_end    = (yrng.reset_end   - this.bias)*this.stretch

    const bottom = src.data['bottom'] as number[]
    let ind1: number = 1, ind2: number = 0
    if(bottom.length >= 2)
    {
        let delta = bottom[1]-bottom[0]
        ind1 = Math.min(bottom.length, Math.max(0, (yrng.start-bottom[0])/delta-1))
        ind2 = Math.min(bottom.length, Math.max(0, (yrng.end-bottom[0])/delta+1))
    }

    if(ind1 >= ind2) {
        cycles.end = 0
        frames.end = 0
    } else {
        frames.end = Math.max.apply(Math, (src.data['frames'] as number[]).slice(ind1, ind2))+1
        cycles.end = Math.max.apply(Math, (src.data['cycles'] as number[]).slice(ind1, ind2))+1
    }
}

on_change_raw_bounds(frng:Range1d, trng:Range1d): void {
    trng.reset_start = frng.reset_start/this.framerate
    trng.reset_end   = frng.reset_end/this.framerate
    trng.start       = frng.start/this.framerate
    trng.end        = frng.end  /this.framerate
}

on_change_peaks_table(peaks:ColumnDataSource): void {
    if(this.updating != '')
        return

    const zval  = peaks.data['z']
    const bases = peaks.data['bases']
    if(zval[0] == zval[1] || bases[0] == bases[1])
        return

    const aval = (bases[1]-bases[0])/(zval[1]-zval[0])
    const bval = zval[0] - bases[0]/aval

    if(Math.abs(aval - this.stretch) < 1e-2 && Math.abs(bval-this.bias) < 1e-5)
        return

    this.stretch   = aval
    this.bias      = bval
    this.updating  = 'table'
}

on_change_stretch(stretch: {value: number}): void {
    if(this.updating != '')
        return

    if(Math.abs(stretch.value - this.stretch) < 1e-2)
        return

    this.stretch  = stretch.value
    this.updating = 'stretch'
}

on_change_bias(bias: {value: number}): void {
    if(this.updating != '')
        return

    if(Math.abs(bias.value - this.bias) < 1e-5)
        return

    this.bias     = bias.value
    this.updating = 'bias'
}

on_change_hover(
    table:   ColumnDataSource,
    stretch: {value: number},
    bias:    {value: number},
    fig:     Plot,
    ttip:    ColumnDataSource
): void {
    if(this.updating == '')
        return

    if(this.updating != 'table') {
        let bases = table.data["bases"] as any as [number, number]
        let aval  = bases[0] / this.stretch + this.bias
        let bval  = bases[1] / this.stretch + this.bias
        let zdata = table.data["z"] as any as [number, number]
        if(
            Math.abs(aval-zdata[0]) < 1e-5 &&
            Math.abs(bval-zdata[1]) < 1e-5
        )
            return

        table.data["z"] = [aval, bval]
        table.properties.data.change.emit()
    }

    if(this.updating != 'stretch')
        stretch.value = this.stretch

    if(this.updating != 'bias')
        bias.value = this.bias

    this.apply_update(fig, ttip)
}
