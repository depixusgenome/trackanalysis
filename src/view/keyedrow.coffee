import * as _         from "underscore"
import * as $         from "jquery"
import * as p         from "core/properties"
import {RowView, Row} from "models/layouts/row"

export class DpxKeyedRowView extends RowView
    className: "dpx-bk-grid-row"
    initialize: (options) ->
        super()
        @$el.attr("tabindex", 1)
        @$el.keydown((evt) => @model.dokeydown(evt))
        @$el.keyup((evt) => @model.dokeyup(evt))

export class DpxKeyedRow extends Row
    default_view: DpxKeyedRowView
    type: "DpxKeyedRow"

    _fig:      ()     -> @children[0]
    _get_tool: (name) ->
        tools = @_fig().toolbar.tools
        for attr in tools
            if attr.type == name
                return attr
        return null

    _set_active: (name) ->
        tool               = @_get_tool(name)

        if tool?
            @_curr         = @_fig().toolbar.gestures.pan.active
            @_curr?.active = false
            tool.active    = true

    _do_zoom: (zoomin, rng) ->
        center = (rng.end+rng.start)*.5
        delta  = rng.end-rng.start
        if zoomin
            delta  /= @zoomrate
        else
            delta  *= @zoomrate

        rng.start = center - delta*.5
        rng.end   = center + delta*.5

        if rng.bounds[0] > rng.start
            rng.start = rng.bounds[0]
        if rng.bounds[1] < rng.end
            rng.end   = rng.bounds[1]

    _do_pan: (panlow, rng) ->
        delta     = (rng.end-rng.start)*@panrate*(if panlow then -1 else 1)
        if rng.bounds[0] > rng.start + delta
            delta = rng.bounds[0]-rng.start
        if rng.bounds[1] < rng.end   + delta
            delta = rng.bounds[1]-rng.end

        rng.start = rng.start + delta
        rng.end   = rng.end   + delta

    _do_reset: () ->
        fig       = @_fig()
        rng       = fig.x_range
        rng.start = rng.bounds[0]
        rng.end   = rng.bounds[1]

        rng       = fig.y_range
        rng.start = rng.bounds[0]
        rng.end   = rng.bounds[1]

    dokeydown: (evt) ->
        if not (@_fig()?)
            return

        val = ""
        for name, kw of {alt: "Alt"; shift: "Shift"; ctrl: "Control"; meta: "Meta"}
            if evt[name+"Key"]
                 val += "#{kw}-"
        val = if val == (evt.key+"-") then evt.key else val + evt.key

        if @keys[val]?
            evt.preventDefault()
            evt.stopPropagation()
            val = @keys[val]
            if val == "reset"
                @_do_reset()

            else if val == "zoom"
                @_set_active("BoxZoomTool")

            else if val == "pan"
                @_set_active("PanTool")

            else
                [tool,axis,dir] = val.split(".")
                @["_do_"+tool](dir == "low", @_fig()[axis+"_range"])

    dokeyup: (evt) ->
        @_curr?.active = true
        @_curr         = null

    @internal {
        _curr:    [p.Any, null]
    }

    @define {
        keys:     [p.Any,   {}]
        zoomrate: [p.Number, 0]
        panrate:  [p.Number, 0]
    }
