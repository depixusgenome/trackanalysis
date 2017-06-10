import *        as $    from "jquery"
import *        as p    from "core/properties"
import {Model}          from "model"
import {BokehView} from "core/bokeh_view"

export class DpxLoadedView extends BokehView

export class DpxLoaded extends Model
    default_view: DpxLoadedView
    type:         "DpxLoaded"
    constructor : (attributes, options) ->
        super(attributes, options)
        $((e) => @done = 1)
    @define { done: [p.Number, 0] }
