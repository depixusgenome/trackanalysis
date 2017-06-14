import {build_views}    from "core/build_views"
import {logger}         from "core/logging"
import * as p           from "core/properties"

import {LayoutDOMView, LayoutDOM} from "models/layouts/layout_dom"

export class DpxToolbarView extends LayoutDOMView
    tagName: "div"
    events: {
        "click .dpx-tb-open": "on_open"
        "click .dpx-tb-save": "on_save"
        "click .dpx-tb-quit": "on_quit"
        "click .dpx-tb-del":  "on_del"
        "change .dpx-tb-bead": "on_bead"
        "change .dpx-tb-discarded": "on_discarded"
    }

    on_open:    () ->
        @model.open = @model.open+1
    on_save:    () ->
        @model.save = @model.save+1
    on_quit:    () ->
        @model.quit = @model.quit+1
    on_bead:    () ->
        @model.bead = @$el.find('.dpx-tb-bead').val()
    on_discarded: () ->
        @model.discarded = @$el.find('.dpx-tb-discarded').val()
    on_discard: () ->
        val = @$el.find('.dpx-tb-bead').val()
        @model.discarded = @$el.find('.dpx-tb-discarded').val()+", #{val}"

    initialize: (options) ->
        super(options)
        @render()
        @listenTo(@model, 'change', @render)

    render: () ->
        super()

export class DpxToolbar extends LayoutDOM
    type: 'DpxToolbar'
    default_view: DpxToolbarView
    @define {
        quit:       [p.Bool, True]
        click:      [p.Number, 0]
        input:      [p.String, '']
        bead:       [p.Number, -1]
        discarded:  [p.String, '']
    }

