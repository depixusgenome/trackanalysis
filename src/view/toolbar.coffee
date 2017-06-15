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
        "click .dpx-tb-del":  "on_discard_current"
        "change .dpx-tb-bead": "on_bead"
        "change .dpx-tb-discard": "on_discard"
        "change .dpx-tb-message": "on_message"
    }

    on_open:    () ->
        @model.open = @model.open+1

    on_save:    () ->
        @model.save = @model.save+1

    on_quit:    () ->
        @model.quit = @model.quit+1

    on_bead:    () ->
        @model.bead = @$el.find('.dpx-tb-bead').val()

    on_discard_current: () ->
        val = @$el.find('.dpx-tb-bead').val()
        @model.discarded = @$el.find('.dpx-tb-discarded').val()+", #{val}"

    on_discard: () ->
        @model.discarded = @$el.find('.dpx-tb-discarded').val()

    on_message: () ->
        @model.message = @$el.find('.dpx-tb-message').val()

    initialize: (options) ->
        super(options)
        @render()
        @listenTo(@model, 'change', @render)

    render: () ->
        super()
        mdl   = @model
        btn   = ['<td><button type="button" style="margin-right: 5px; width: 20px;"'+
                 ' class="dpx-tb-open bk-bs-btn bk-bs-btn-default">',
                 '</button></td>']
        bead  = '<td><label for=".dpx-tb-bead" style="margin-right: 5px">'      +
                'Bead</label></td>'                                             +
                '<td><input class="dpx-tb-bead bk-widget-form-input"'           +
                ' type="number"'                                                +
                "min=0  max=10000 step=1  value=#{mdl.bead}></td>"
        disc  = '<td><label for=".dpx-tb-discard" style="margin-right: 5px">'   +
                'Discarded</label></td>'                                        +
                '<td><input class="dpx-tb-bead bk-widget-form-input"'           +
                " type='text' value=#{mdl.discarded}></td>"
        rej   = '<td><button type="button" style="margin-right: 5px; width: 200px;"'+
                ' class="dpx-tb-del bk-bs-btn bk-bs-btn-default">'                  +
                '-</button></td>'
        msg   = '<td><label for=".dpx-tb-message" style="margin-right: 5px">'   +
                "#{mdl.message}</label></td>"
        html  = '<table><tr>'           +
                btn[0]+'Open'+btn[1]    +
                btn[0]+'Save'+btn[1]    +
                bead + discarded + rej  +
                msg                     +
                btn[0]+'Quit'+btn[1]
        @$el.html("<table class='dpx-tb'> #{html}</table>")
        if mdl.disabled then
            @$el.find('.dpx-tb-save').prop('disabled', true)
            @$el.find('.dpx-tb-bead').prop('disabled', true)
            @$el.find('.dpx-tb-discard').prop('disabled', true)
            @$el.find('.dpx-tb-del').prop('disabled', true)
        return @

export class DpxToolbar extends LayoutDOM
    type: 'DpxToolbar'
    default_view: DpxToolbarView
    @define {
        click:      [p.Number,  0]
        bead:       [p.Number,  -1]
        discarded:  [p.String,  '']
        message:    [p.String,  '']
        disabled:   [p.Bool,    false]
    }

