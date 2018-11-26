import * as p  from "core/properties"
import {HoverTool, HoverToolView} from "models/tools/inspectors/hover_tool"
import {GlyphRenderer}            from "models/renderers/glyph_renderer"


export class NAMEView extends HoverToolView
    _update: ([renderer_view, {geometry}]) ->
        if not @model.active
            return

        man  = renderer_view.model.get_selection_manager()
        tmp  = man.inspectors[renderer_view.model.id]
        if (renderer_view.model instanceof GlyphRenderer)
            tmp = renderer_view.model.view.convert_selection_to_subset(tmp)

        if tmp.is_empty()
            return

        inds = tmp.indices
        if inds?.length > 1
            inds.sort((a,b) => a - b)
            if inds.length > @model.maxcount
                ind = Math.floor((inds.length - @model.maxcount)*0.5)
                tmp.indices = inds.slice(ind, ind+@model.maxcount)
        super([renderer_view, {geometry}])
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
