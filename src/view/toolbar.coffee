import {build_views}    from "core/build_views"
import {logger}         from "core/logging"
import * as p           from "core/properties"
import * as $           from "jquery"

import {LayoutDOMView, LayoutDOM} from "models/layouts/layout_dom"

export class DpxToolbarView extends LayoutDOMView
    tagName: "div"

    on_frozen:  () ->
        elem = $(@el)
        elem.find('.dpx-tb-save')   .prop('disabled', @model.frozen)
        elem.find('.dpx-tb-bead')   .prop('disabled', @model.frozen)
        elem.find('.dpx-tb-discard').prop('disabled', @model.frozen)
        elem.find('.dpx-tb-del')    .prop('disabled', @model.frozen)

    on_message: () ->
        $(@el).find('.dpx-tb-message').val(@model.message)

    on_bead:    () ->
        val = $(@el).find('.dpx-tb-bead').val()
        @model.bead = parseInt(val)

    on_open: () ->
        console.log('*************')
        @model.open = @model.open+1

    on_discard_current: () ->
        ele = $(@el)
        val = ele.find('.dpx-tb-bead').val()
        @model.discarded = ele.find('.dpx-tb-discarded').val()+", .{val}"

    on_discard: () ->
        @model.discarded = $(@el).find('.dpx-tb-discarded').val()

    initialize: (options) ->
        super(options)
        @render()
        @listenTo(@model,         'change', @render)
        @listenTo(@model.frozen,  'change', () => @on_frozen())
        @listenTo(@model.message, 'change', () => @on_message())

    make_btn: (name, label, width = '60px') ->
        str = "<td><button type='button' style='width:#{width};height:25px;'" +
              " class='dpx-tb-#{name} bk-bs-btn bk-bs-btn-default'"           +
              ">#{label}</button></td>"
        return str

    render: () ->
        super()
        mdl   = @model
        bead  = '<td><label for=".dpx-tb-bead" style="margin-left: 5px">' +
                'Bead</label></td>'                                        +
                '<td><input class="dpx-tb-bead bk-widget-form-input"'      +
                ' type="number" style="width: 60px; height: 25px"'         +
                "min=0  max=10000 step=1  value=#{mdl.bead}></td>"
        disc  = '<td><label for=".dpx-tb-discard" style="margin-left: 1px">' +
                'Discarded</label></td>'                                     +
                '<td><input class="dpx-tb-bead bk-widget-form-input"'        +
                ' type="text" style="width: 60px; height: 25px" '            +
                "value=#{mdl.discarded}></td>"
        msg   = '<td><label for=".dpx-tb-message"'         +
                ' style="margin-right: 5px; width=200px">' +
                "#{mdl.message}</label></td>"
        html  = '<table><tr>'+ @make_btn('open', 'Open')   +
                @make_btn('save', 'Save')                  +
                bead + disc + @make_btn('del', '━', '5px') + msg

        if @model.hasquit
            html = html + @make_btn('quit', 'Quit')

        elem = $(@el)
        elem.html("<table class='dpx-tb'> #{html}</table>")
        elem.find('.dpx-tb-open').click(() => @on_open())
        elem.find('.dpx-tb-save').click(() => @model.save = @model.save+1)
        elem.find('.dpx-tb-quit').click(() => @model.quit = @model.quit+1)
        elem.find('.dpx-tb-del') .click(() => @on_discard_current())
        elem.find('.dpx-tb-bead').change(() => @on_bead())
        elem.find('.dpx-tb-discard').change(() => @on_discard())

        @on_frozen()
        return @

export class DpxToolbar extends LayoutDOM
    type: 'DpxToolbar'
    default_view: DpxToolbarView
    @define {
        open:       [p.Number,  0]
        save:       [p.Number,  0]
        quit:       [p.Number,  0]
        bead:       [p.Number,  -1]
        discarded:  [p.String,  '']
        message:    [p.String,  '']
        frozen:     [p.Bool,    false]
        hasquit:    [p.Bool,    false]
    }
