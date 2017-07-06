import * as p  from "core/properties"
import {HoverTool, HoverToolView} from "models/tools/inspectors/hover_tool"

export class DpxHoverToolView extends HoverToolView
    _update: ([indices, tool, renderer, ds, {geometry}]) ->
        if not @model.active
          return
        inds = indices['1d'].indices
        if inds?.length > 1
            inds.sort((a,b) => a - b)
            if inds.length > @model.maxcount
                ind = Math.floor((inds.length - @model.maxcount)*0.5)
                indices['1d'].indices = inds.slice(ind, ind+@model.maxcount)
        super([indices, tool, renderer, ds, {geometry}])

export class DpxHoverTool extends HoverTool
    default_view: DpxHoverToolView
    @define { maxcount: [ p.Int, 5] }
