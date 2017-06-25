import {build_views}    from "core/build_views"
import {logger}         from "core/logging"
import * as p           from "core/properties"
import * as $           from "jquery"

import {LayoutDOMView, LayoutDOM} from "models/layouts/layout_dom"

export class DpxToolbarView extends LayoutDOMView
    tagName: "div"

    on_bead:    () ->
        val = $(@el).find('#dpx-tb-bead').val()
        @model.bead = parseInt(val)

    on_discard_current: () ->
        ele = $(@el)
        val = ele.find('#dpx-tb-bead').val()
        @model.discarded = ele.find('#dpx-tb-discard').val()+",#{val}"

    on_discard: () ->
        @model.discarded = $(@el).find('#dpx-tb-discard').val()

    on_change_frozen:  () ->
        $(@el).find('.dpx-tb-freeze').prop('disabled', @model.frozen)

    on_change_bead: () ->
        val = "#{@model.bead}"
        $(@el).find('#dpx-tb-bead').val(val)

    on_change_discarded: () ->
        $('#dpx-tb-discard').val("'#{@model.discarded}'")

    on_change_message: () ->
        $(@el).find('#dpx-tb-message').html(@model.message)

    initialize: (options) ->
        super(options)
        @render()
        @listenTo(@model, 'change:bead',      () => @on_change_bead())
        @listenTo(@model, 'change:discarded', () => @on_change_discarded())
        @listenTo(@model, 'change:message',   () => @on_change_message())
        @listenTo(@model, 'change:frozen',    () => @on_change_frozen())

    make_btn: (name, label, freeze = 'dpx-tb-freeze') ->
        str = "<button type='button' id='dpx-tb-#{name}' "+
              "class='#{freeze} bk-bs-btn bk-bs-btn-default'>#{label}</button>"
        return str

    render: () ->
        super()
        mdl  = @model
        if @model.hasquit
            quit = "<div class='dpx-col-12'>#{@make_btn('quit', 'Quit')}</div>"
        else
            quit =''

        html = "<div class='dpx-row dpx-tb'><span>"+
                    "#{@make_btn('open', 'Open', '')}"+
                    "#{@make_btn('save', 'Save')}"+
                    "<label>Bead</label>"+
                    "<input id='dpx-tb-bead'"+
                        " class='dpx-tb-freeze bk-widget-form-input'"+
                        " type='number' min=0  max=10000 step=1  value=#{mdl.bead}>"+
                    "<label>Discarded</label>"+
                    "<input id='dpx-tb-discard'"+
                        " class='dpx-tb-freeze bk-widget-form-input'"+
                        " type='text' value='#{mdl.discarded}'>"+
                    "#{@make_btn('del', '━', true)}"+
                    "<div id='dpx-tb-message' class='bk-markup'>"+
                        "#{mdl.message}</div>"+
                    "#{quit}</span></div>"

        elem = $(@el)
        elem.html(html)
        elem.find('#dpx-tb-open').click(() => @model.open = @model.open+1)
        elem.find('#dpx-tb-save').click(() => @model.save = @model.save+1)
        elem.find('#dpx-tb-quit').click(() => @model.quit = @model.quit+1)
        elem.find('#dpx-tb-del') .click(() => @on_discard_current())
        elem.find('#dpx-tb-bead').change(() => @on_bead())
        elem.find('#dpx-tb-discard').change(() => @on_discard())

        @on_change_frozen()
        return @

export class DpxToolbar extends LayoutDOM
    type: 'DpxToolbar'
    default_view: DpxToolbarView
    @define {
        frozen:     [p.Bool,    true]
        open:       [p.Number,  0]
        save:       [p.Number,  0]
        quit:       [p.Number,  0]
        bead:       [p.Number,  -1]
        discarded:  [p.String,  '']
        message:    [p.String,  '']
        hasquit:    [p.Bool,    false]
    }
