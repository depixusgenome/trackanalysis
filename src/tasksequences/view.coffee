import * as p  from "core/properties"
import {HoverTool, HoverToolView} from "models/tools/inspectors/hover_tool"
import {GlyphRenderer}            from "models/renderers/glyph_renderer"


export class NAMEView extends HoverToolView
    _update: ([renderer_view, {geometry}]) ->
        if @model.active
            super([renderer_view, {geometry}])
            ttip = @ttmodels[renderer_view.model.id]
            if ttip.data.length > @model.maxcount
                ind       = Math.floor((ttip.data.length-@model.maxcount)/2)
                ttip.data = ttip.data.slice(ind, ind + @model.maxcount)
        return null

export class NAME extends HoverTool
    default_view: NAMEView
    type: "NAME"

    setsource: (source, value) ->
        if @_callcount != value
            return
        if @updating   != ''
            return

        @_callcount = value
        tmp = source.data["values"]
        source.data["z"] = tmp.map(((x)-> x/@stretch+@bias), @)
        source.properties.data.change.emit()

    apply_update: (fig, ttip) ->
        if @updating == ''
            return

        @_callcount = @_callcount + 1

        bases       = fig.extra_y_ranges['bases']
        yrng        = fig.y_range
        bases.start = (yrng.start - @bias) * @stretch
        bases.end   = (yrng.end   - @bias) * @stretch
        bases.reset_start = (yrng.reset_start - @bias) * @stretch
        bases.reset_end   = (yrng.reset_end   - @bias) * @stretch

        window.setTimeout(((b, c) => @setsource(b, c)),
                          800, ttip, @_callcount)
        @updating   = ''

    @define {
        maxcount  : [ p.Int, 3],
        framerate : [p.Number, 1],
        stretch   : [p.Number, 0],
        bias      : [p.Number, 0],
        updating  : [p.String, '']
    }

    @internal { _callcount: [p.Number, 0] }
