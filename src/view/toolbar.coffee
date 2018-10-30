import {build_views}    from "core/build_views"
import {logger}         from "core/logging"
import * as p           from "core/properties"

import {WidgetView, Widget} from "models/widgets/widget"

export class DpxToolbarView extends WidgetView
    tagName: "div"

    on_bead:    () ->
        val = $(@el).find('#dpx-tb-bead').val()
        @model.bead = parseInt(val)

    on_discard_current: () ->
        @model.currentbead = !@model.currentbead

    on_selection: () ->
        @model.seltype = !@model.seltype
        @on_change_discarded()

    on_discard: () ->
        if @model.seltype
            @model.discarded = $(@el).find('#dpx-tb-discard').val()
        else
            @model.accepted  = $(@el).find('#dpx-tb-discard').val()

    on_change_frozen:  () ->
        $(@el).find('.dpx-freeze').prop('disabled', @model.frozen)

    on_change_bead: () ->
        val = "#{@model.bead}"
        $(@el).find('#dpx-tb-bead').val(val)

    on_change_discarded: () ->
        if @model.seltype
            $('#dpx-tb-discard').val("#{@model.discarded}")
            $('#dpx-tb-selection').html('=')
        else
            $('#dpx-tb-discard').val("#{@model.accepted}")
            $('#dpx-tb-selection').html('≠')

    on_change_message: () ->
        $(@el).find('#dpx-tb-message').html(@model.message)

    connect_signals: () ->
        super()
        @connect(@model.properties.bead.change,      () => @on_change_bead())
        @connect(@model.properties.discarded.change, () => @on_change_discarded())
        @connect(@model.properties.message.change,   () => @on_change_message())
        @connect(@model.properties.frozen.change,    () => @on_change_frozen())
        @connect(@model.properties.filelist.change,  () => @render())

    make_btn: (name, label, ttip = '', freeze = 'dpx-freeze') ->
        if ttip == ''
            str = "<button type='button' id='dpx-tb-#{name}' "+
                  "class='#{freeze} bk-bs-btn bk-bs-btn-default'>#{label}</button>"
        else
            str = "<button type='button' id='dpx-tb-#{name}' "+
                  "class='#{freeze} bk-bs-btn bk-bs-btn-default' "+
                  "data-balloon='#{ttip}' "+
                    'data-balloon-length="medium" data-balloon-pos="right">'+
                  label+'</button>'
        return str

    make_filelist: () ->
        itm = '<div id="dpx-tb-flist">'+
                '<button type="button" class="bk-bs-btn bk-bs-btn-default"'+
                    ' id="dpx-tb-flist-btn">'+
                    '<span class="bk-bs-caret"/>'+
                '</button>'+
                '<div id="dpx-tb-flist-menu"><table>'
        if @model.filelist.length > 0
            for j in [0..@model.filelist.length-1]
                itm += '<tr><td><label class="bk-bs-radio"><input'
                if j == @model.currentfile
                    itm += ' checked=true'
                itm += " type='radio' id='dpx-tb-flist-#{j}' class='dpx-tb-flist-itm'/>"+
                       "#{@model.filelist[j]}</label></td>"+
                       "<td><button type='button' class='bk-bs-btn bk-bs-btn-danger' "+
                       "id='dpx-tb-flist-btn-#{j}' class='dpx-tb-flist-itm'>X</button></td>"+
                       "</tr>"

        itm += '</table></div></div>'
        return itm

    on_click_del_file: (evt) ->
        evt.preventDefault()
        evt.stopPropagation()

        tmp            = evt.target.id.split('-')
        @model.delfile = Number(tmp[tmp.length-1])

    on_click_file: (evt) ->
        evt.preventDefault()
        evt.stopPropagation()

        tmp = evt.target.id.split('-')
        id  = Number(tmp[tmp.length-1])
        if id == @model.currentfile
            return

        $(@el).find("#dpx-tb-flist-#{@model.currentfile}").prop('checked', false)
        $(@el).find("#dpx-tb-flist-#{id}").prop('checked', true)
        @model.currentfile = Number(id)

    render: () ->
        super()
        mdl  = @model
        if @model.hasquit
            quit = "<div class='dpx-col-12'>#{@make_btn('quit', 'Quit', '', '')}</div>"
        else
            quit =''

        ttips = ['Open an analysis, i.e. ".ana" extension, or a track file and '+
                 'then its ".gr" files',
                 'Select opened files',
                 'Save an analysis, i.e. ".ana" extension, or create an xlsx report',
                 'Change wether to discard (=) or select (≠) specific beads',
                 'Remove the current bead']

        html = @make_btn('open', 'Open', ttips[0], '')+
               @make_filelist()+
               @make_btn('save', 'Save', ttips[2])+
               "<label>Bead</label>"+
               "<input id='dpx-tb-bead'"+
                   " class='dpx-freeze bk-widget-form-input'"+
                   " type='number' min=0  max=10000 step=1  value=#{mdl.bead}>"+
               "<label>Discarded</label>"+
               @make_btn('selection', '=', ttips[3])+
               "<input id='dpx-tb-discard'"+
                   " class='dpx-freeze bk-widget-form-input'"+
                   " type='text' value='#{mdl.discarded}'>"+
               @make_btn('del', '━', ttips[4])+
               "<div id='dpx-tb-message' class='bk-markup'>"+
                   "#{mdl.message}</div>"+
               "#{quit}"

        elem = $(@el)
        elem.html(html)
        elem.find('#dpx-tb-open').click(() => @model.open = @model.open+1)
        elem.find('#dpx-tb-save').click(() => @model.save = @model.save+1)
        elem.find('#dpx-tb-quit').click(() => @model.quit = @model.quit+1)
        elem.find('#dpx-tb-del') .click(() => @on_discard_current())
        elem.find('#dpx-tb-bead').change(() => @on_bead())
        elem.find('#dpx-tb-discard').change(() => @on_discard())
        elem.find('#dpx-tb-selection').click(() => @on_selection())
        if @model.filelist.length > 0
            for i in [0..@model.filelist.length-1]
                elem.find("#dpx-tb-flist-#{i}").change((e) => @on_click_file(e))
                elem.find("#dpx-tb-flist-btn-#{i}").click((e) => @on_click_del_file(e))

        @on_change_frozen()
        return @

  get_width_height: () ->
      [width, height] = LayoutDOMView::get_width_height()
      return [width, 40]

  get_height: () -> 40

export class DpxToolbar extends Widget
    type: 'DpxToolbar'
    default_view: DpxToolbarView

    initialize: (attributes, options) ->
        super(attributes, options)
        @css_classes = ["dpx-row", "dpx-widget", "dpx-tb", "dpx-span"]

    @define {
        frozen:     [p.Bool,    true]
        open:       [p.Number,  0]
        currentfile:[p.Number,  -1]
        delfile:    [p.Number,  -1]
        filelist:   [p.Array,   []]
        save:       [p.Number,  0]
        quit:       [p.Number,  0]
        bead:       [p.Number,  -1]
        discarded:  [p.String,  '']
        accepted:   [p.String,  '']
        currentbead:[p.Bool,    true]
        seltype:    [p.Bool,    true]
        message:    [p.String,  '']
        hasquit:    [p.Bool,    false]
    }
