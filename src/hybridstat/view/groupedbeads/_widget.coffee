import * as p           from "core/properties"

import {WidgetView, Widget} from "models/widgets/widget"

export class DpxDiscardedBeads extends WidgetView
    tagName: "div"

    on_discard: () ->
        if @model.seltype
            @model.discarded = $(@el).find('#dpx-gb-discard').val()
        else
            @model.accepted  = $(@el).find('#dpx-gb-discard').val()

    on_selection: () ->
        @model.seltype = !@model.seltype
        @on_change_discarded()

    on_change_frozen:  () ->
        $(@el).find('.dpx-freeze').prop('disabled', @model.frozen)

    on_change_discarded: () ->
        if @model.seltype
            $('#dpx-gb-discard').val("#{@model.discarded}")
            $('#dpx-gb-selection').html('=')
        else
            $('#dpx-gb-discard').val("#{@model.accepted}")
            $('#dpx-gb-selection').html('≠')

    connect_signals: () ->
        super()
        @connect(@model.properties.discarded.change, () => @on_change_discarded())

    make_btn: (name, label, ttip = '', freeze = 'dpx-freeze') ->
        if ttip == ''
            str = "<button type='button' id='dpx-gb-#{name}' "+
                  "class='#{freeze} bk-bs-btn bk-bs-btn-default'>#{label}</button>"
        else
            str = "<button type='button' id='dpx-gb-#{name}' "+
                  "class='#{freeze} bk-bs-btn bk-bs-btn-default' "+
                  "data-balloon='#{ttip}' "+
                    'data-balloon-length="medium" data-balloon-pos="right">'+
                  label+'</button>'
        return str

    _icon: (label) ->
        return '<i class="icon-dpx-'+label+'"></i>'

    render: () ->
        super()
        mdl  = @model
        ttips = ['Change wether to discard (=) or select (≠) specific beads']
        html = @make_btn('selection', '=', ttips[0])+
               "<input id='dpx-gb-discard'"+
                   " class='dpx-freeze bk-widget-form-input'"+
                   " type='text' value='#{mdl.discarded}' placeholder='#{mdl.helpmessage}'>"

        elem = $(@el)
        elem.html(html)
        elem.find('#dpx-gb-discard').change(() => @on_discard())
        elem.find('#dpx-gb-selection').click(() => @on_selection())

        @on_change_frozen()
        return @

    get_width_height: () ->
        [width, height] = LayoutDOMView::get_width_height()
        return [width, 30]

    get_height: () -> 30

export class DpxDiscardedBeads extends Widget
    type: 'DpxDiscardedBeads'
    default_view: DpxDiscardedBeadsView

    initialize: (attributes, options) ->
        super(attributes, options)
        @css_classes = ["dpx-row", "dpx-widget", "dpx-gb-widget", "dpx-span"]

    @define {
        frozen:      [p.Bool,    true],
        discarded:   [p.String,  ''],
        accepted:    [p.String,  ''],
        seltype:     [p.Bool,    true],
        helpmessage: [p.String, '']
    }
