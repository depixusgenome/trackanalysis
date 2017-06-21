import {build_views}    from "core/build_views"
import {logger}         from "core/logging"
import * as p           from "core/properties"
import * as $           from "jquery"

import {LayoutDOMView, LayoutDOM} from "models/layouts/layout_dom"

export class DpxToolbarView extends LayoutDOMView
    tagName: "div"

    on_bead:    () ->
        val = $(@el).find('.dpx-tb-bead').val()
        @model.bead = parseInt(val)

    on_discard_current: () ->
        ele = $(@el)
        val = ele.find('.dpx-tb-bead').val()
        @model.discarded = ele.find('.dpx-tb-discarded').val()+", .{val}"

    on_discard: () ->
        @model.discarded = $(@el).find('.dpx-tb-discarded').val()

    on_change_frozen:  () ->
        $(@el).find('.dpx-tb-freeze').prop('disabled', @model.frozen)

    on_change_bead: () ->
        val = "#{@model.bead}"
        $(@el).find('.dpx-tb-bead').val(val)

    on_change_discarded: () ->
        $(@el).find('.dpx-tb-discarded').val(@model.discarded)

    on_change_message: () ->
        $(@el).find('.dpx-tb-message').html(@model.message)

    initialize: (options) ->
        super(options)
        @render()
        @listenTo(@model, 'change:bead',      () => @on_change_bead())
        @listenTo(@model, 'change:discarded', () => @on_change_discarded())
        @listenTo(@model, 'change:message',   () => @on_change_message())
        @listenTo(@model, 'change:frozen',    () => @on_change_frozen())

    make_btn: (name, label, freeze = true, style = 'width: 60px;') ->
        str = "<button type='button' style='#{style}'"+
              " class='dpx-tb-#{name} bk-bs-btn bk-bs-btn-default'"+
              ">#{label}</button>"
        if freeze
            $(str).addClass('dpx-tb-freeze')
        return str

    render: () ->
        super()
        mdl  = @model
        if @model.hasquit
            quit = @make_btn('quit', 'Quit', 'width: 60px; align-self: right;')
        else
            quit =''

        html = "<table class='dpx-tb' style='width: 100vw'><tr style='width: 100vw'>"+
               "<td style='width: 60px'> #{@make_btn('open', 'Open', false)} </td>"+
               "<td style='width: 60px'> #{@make_btn('save', 'Save')} </td>"+
               "<td style='width: 20px'>"+
                   "<label for='.dpx-tb-bead' style='margin-left: 5px'>Bead</label>"+
               "</td>"+
               "<td style='width: 40px'>"+
                   "<input class='dpx-tb-bead dpx-tb-freeze bk-widget-form-input'"+
                         " type='number' style='width: 40px; height: 28px;'"+
                         " min=0  max=10000 step=1  value=#{mdl.bead}>"+
               "</td>"+
               "<td style='width: 20px'>"+
                    "<label for='.dpx-tb-discard' style='margin-left: 1px'>Discarded</label>"+
               "</td>"+
               "<td style='width: 60px'>"+
                    "<input class='dpx-tb-bead dpx-tb-freeze bk-widget-form-input'"+
                          " type='text' style='width: 60px; height: 28px'"+
                          " value=#{mdl.discarded}>"+
               "</td>"+
               "<td style='width: 5px'>"+
                    "#{@make_btn('del', '━', true, 'width: 5px')}"+
               "</td>"+
               "<td style='width:auto'>"+
                    "<div class='dpx-tb-message bk-markup'"+
                        " style='margin-right: 5px;margin-left: 5px;align-self: center;"+
                                "width:auto;height: 28px;'>"+
                        "#{mdl.message}"+
                    "</div>"+
               "</td>"+
               "<td style='width:auto'>#{quit}</td>"+
               "</tr></table>"

        elem = $(@el)
        elem.html(html)
        elem.find('.dpx-tb-open').click(() => @model.open = @model.open+1)
        elem.find('.dpx-tb-save').click(() => @model.save = @model.save+1)
        elem.find('.dpx-tb-quit').click(() => @model.quit = @model.quit+1)
        elem.find('.dpx-tb-del') .click(() => @on_discard_current())
        elem.find('.dpx-tb-bead').change(() => @on_bead())
        elem.find('.dpx-tb-discard').change(() => @on_discard())

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
