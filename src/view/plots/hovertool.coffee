import * as p  from "core/properties"
import {HoverTool, HoverToolView} from "models/tools/inspectors/hover_tool"
import {GlyphRenderer}            from "models/renderers/glyph_renderer"

export class DpxHoverToolView extends HoverToolView
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

export class DpxHoverTool extends HoverTool
    default_view: DpxHoverToolView
    @define { maxcount: [ p.Int, 5] }
