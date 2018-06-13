import *        as p    from "core/properties"
import {Model}          from "model"
import {DOMView} from "core/dom_view"

export class DpxLoadedView extends DOMView
    connect_signals: () ->
        super()
        @connect(@model.properties.resizedfig.change, () => @model.on_resize_figure())

export class DpxLoaded extends Model
    default_view: DpxLoadedView
    type:         "DpxLoaded"
    constructor : (attributes, options) ->
        super(attributes, options)
        $((e) => @done = 1)


    @define { done: [p.Number, 0], resizedfig: [p.Instance, null] }

    on_resize_figure: ()->
        @resizedfig?.resize()
        @resizedfig?.layout()
