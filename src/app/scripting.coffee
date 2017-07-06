import *        as $    from "jquery"
import *        as p    from "core/properties"
import {Model}          from "model"
import {DOMView} from "core/dom_view"

export class DpxLoadedView extends DOMView

export class DpxLoaded extends Model
    default_view: DpxLoadedView
    type:         "DpxLoaded"
    constructor : (attributes, options) ->
        super(attributes, options)
        $((e) => @done = 1)
    @define { done: [p.Number, 0] }
