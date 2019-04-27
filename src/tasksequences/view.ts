import * as p                        from "core/properties"
import {ColumnDataSource}            from "models/sources/column_data_source"
import {Plot}                        from "models/plots/plot"
import {HoverTool, HoverToolView}    from "models/tools/inspectors/hover_tool"
import {RendererView}                from "models/renderers/renderer"
import {PointGeometry, SpanGeometry} from "core/geometry"

export class NAMEView extends HoverToolView {
    model: NAME
    _update(
            [renderer_view, {geometry}]: [
                RendererView,
                {geometry: PointGeometry | SpanGeometry}
            ]
    ): void {
        if (this.model.active)
        {
            super._update([renderer_view, {geometry}])
            const ttip = this.ttmodels[renderer_view.model.id]
            if (ttip.data.length > this.model.maxcount)
            {
                const ind = Math.floor((ttip.data.length-this.model.maxcount)/2)
                ttip.data = ttip.data.slice(ind, ind + this.model.maxcount)
            }
        }
    }
}

export namespace NAME {
    export type Attrs = p.AttrsOf<Props>

    export type Props = HoverTool.Props & {
        _callcount : p.Property<number>
        maxcount   : p.Property<number>
        framerate  : p.Property<number>
        stretch    : p.Property<number>
        bias       : p.Property<number>
        updating   : p.Property<string>
    }
}

export interface NAME extends NAME.Attrs {}

export class NAME extends HoverTool {
    properties: NAME.Props
    constructor(attrs?: Partial<NAME.Attrs>) { super(attrs); }

    setsource(source: ColumnDataSource, value:number): void {
        if (this._callcount != value)
            return
        if (this.updating   != '')
            return

        this._callcount  = value
        const tmp        = source.data["values"] as number[]
        source.data["z"] = tmp.map((x:number)=> x/this.stretch+this.bias)
        source.properties.data.change.emit()
    }

    apply_update(fig: Plot, ttip:ColumnDataSource): void {
        if (this.updating == '')
            return

        this._callcount = this._callcount + 1

        const bases       = fig.extra_y_ranges['bases'] as Range1d
        const yrng        = fig.y_range as Range1d
        bases.start       = (yrng.start - this.bias) * this.stretch
        bases.end         = (yrng.end   - this.bias) * this.stretch
        bases.reset_start = (yrng.reset_start - this.bias) * this.stretch
        bases.reset_end   = (yrng.reset_end   - this.bias) * this.stretch

        window.setTimeout(
            ((b:ColumnDataSource, c:number) => this.setsource(b, c)),
            800, ttip, this._callcount
        )
        this.updating   = ''
    }

    static initClass(): void {
        this.prototype.default_view = NAMEView
        this.prototype.type         = "NAME"

        this.define<NAME.Props>({
            maxcount  : [ p.Int, 3],
            framerate : [p.Number, 1],
            stretch   : [p.Number, 0],
            bias      : [p.Number, 0],
            updating  : [p.String, '']
        })

        this.internal({ _callcount: [p.Number, 0] })
    }
}
NAME.initClass()
