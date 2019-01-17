import * as p         from "core/properties"
import {RowView, Row} from "models/layouts/row"
import {ToolbarBox}   from "models/tools/toolbar_box"

export class DpxKeyedRowView extends RowView
    className: "dpx-bk-grid-row"
    render: () ->
        super()
        @el.setAttribute("tabindex", 1)
        @el.onkeydown = (evt) => @model.dokeydown(evt)
        @el.onkeyup   = (evt) => @model.dokeyup(evt)

export class DpxKeyedRow extends Row
    default_view: DpxKeyedRowView
    type: "DpxKeyedRow"
    _get_tb: () ->
        if @toolbar?
            return @toolbar

        return @fig.toolbar

    _get_tool: (name) ->
        if @toolbar?
            if @toolbar instanceof ToolbarBox
                for _, gest of @toolbar.toolbar.gestures
                    for proxy in gest.tools
                        for tool in proxy.tools
                            if tool.type == name
                                return proxy
                return null
            else
                tools = @toolbar.tools
        else
            tools = @fig.toolbar.tools

        for attr in tools
            if attr.type == name
                return attr
        return null

    _activate: (tool) ->
        act         = tool.active
        tool.active = not act

    _set_active: (name) ->
        tool = @_get_tool(name)
        if tool?
            tbar = @fig.toolbar
            if @toolbar instanceof ToolbarBox
                tbar = @toolbar.toolbar
            else if @toolbar?
                tbar = @toolbar

            @_curr = tbar.gestures.pan.active
            if @_curr isnt tool
                if @_curr?
                    @_activate(@_curr)

                @_activate(tool)
            else
                @_curr = null

    _do_zoom: (zoomin, rng) ->
        unless rng.bounds?
            return

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
        unless rng.bounds?
            return

        delta     = (rng.end-rng.start)*@panrate*(if panlow then -1 else 1)
        if rng.bounds[0] > rng.start + delta
            delta = rng.bounds[0]-rng.start
        if rng.bounds[1] < rng.end   + delta
            delta = rng.bounds[1]-rng.end

        rng.start = rng.start + delta
        rng.end   = rng.end   + delta

    _do_reset: () ->
        fig       = @fig
        rng       = fig.x_range
        if rng.bounds?
            rng.start = rng.bounds[0]
            rng.end   = rng.bounds[1]

        rng       = fig.y_range
        if rng.bounds?
            rng.start = rng.bounds[0]
            rng.end   = rng.bounds[1]

    dokeydown: (evt) ->
        if not (@fig?)
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
                tool = if val[0...3] == "pan" then "pan" else "zoom"
                rng  = if "x" in val then "x_range" else "y_range"
                dir  = "low" == val[val.length-3...val.length]
                @["_do_#{tool}"](dir, @fig[rng])

    dokeyup: (evt) ->
        if @_curr?
            @_activate(@_curr)
        @_curr  = null

    @internal {
        _curr:    [p.Any, null]
    }

    @define {
        fig:      [p.Instance ]
        toolbar:  [p.Instance, null]
        keys:     [p.Any,   {}]
        zoomrate: [p.Number, 0]
        panrate:  [p.Number, 0]
    }
