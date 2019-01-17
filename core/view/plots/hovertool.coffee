import * as p  from "core/properties"
import {HoverTool, HoverToolView} from "models/tools/inspectors/hover_tool"
import {GlyphRenderer}            from "models/renderers/glyph_renderer"

export class DpxHoverToolView extends HoverToolView
    _update: ([renderer_view, {geometry}]) ->
        if not @model.active
            super([renderer_view, {geometry}])
            ttip = @ttmodels[renderer_view.model.id]
            if ttip.data.length > @model.maxcount
                ind       = Math.floor((ttip.data.length-@model.maxcount)/2)
                ttip.data = ttip.data.slice(ind, ind + @model.maxcount)
        return null

export class DpxHoverTool extends HoverTool
    default_view: DpxHoverToolView
    @define { maxcount: [ p.Int, 5] }
