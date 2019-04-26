import {build_views}    from "core/build_views"
import {logger}         from "core/logging"
import * as p           from "core/properties"

import {WidgetView, Widget} from "models/widgets/widget"
declare function jQuery(...args: any[]): any


export class DpxToolbarView extends WidgetView {
    model: DpxToolbar
    on_bead(): void {
        const val = jQuery(this.el).find('#dpx-tb-bead').val()
        this.model.bead = parseInt(val)
    }

    on_discard_current(): void {
        this.model.currentbead = !this.model.currentbead
    }

    on_selection(): void {
        this.model.seltype = !this.model.seltype
        this.on_change_discarded()
    }

    on_discard() : void {
        if(this.model.seltype)
            this.model.discarded = jQuery(this.el).find('#dpx-tb-discard').val()
        else
            this.model.accepted  = jQuery(this.el).find('#dpx-tb-discard').val()
    }

    on_change_frozen() : void {
        jQuery(this.el).find('.dpx-freeze').prop('disabled', this.model.frozen)
    }

    on_change_bead(): void {
        const val: string = `${this.model.bead}`
        jQuery(this.el).find('#dpx-tb-bead').val(val)
    }
    on_change_discarded(): void {
        if(this.model.seltype) {
            jQuery('#dpx-tb-discard').val(`${this.model.discarded}`)
            jQuery('#dpx-tb-selection').html('=')
        } else {
            jQuery('#dpx-tb-discard').val(`${this.model.accepted}`)
            jQuery('#dpx-tb-selection').html('≠')
        }
    }

    on_change_message() : void {
        jQuery(this.el).find('#dpx-tb-message').html(this.model.message)
    }

    connect_signals(): void {
        super.connect_signals()
        this.connect(this.model.properties.bead.change,      () => this.on_change_bead())
        this.connect(this.model.properties.discarded.change, () => this.on_change_discarded())
        this.connect(this.model.properties.message.change,   () => this.on_change_message())
        this.connect(this.model.properties.frozen.change,    () => this.on_change_frozen())
        this.connect(this.model.properties.filelist.change,  () => this.render())
    }

    make_btn(name: string, label: string, ttip: string = '', freeze: string = 'dpx-freeze') : string {
        let str = ""
        if(ttip == '')
            str = `<button type='button' id='dpx-tb-${name}' `+
                  `class='${freeze} bk-bs-btn bk-bs-btn-default'>${label}</button>`
        else
            str = `<button type='button' id='dpx-tb-${name}' `+
                  `class='${freeze} bk-bs-btn bk-bs-btn-default' `+
                  `data-balloon='${ttip}' `+
                    'data-balloon-length="medium" data-balloon-pos="right">'+
                  label+'</button>'
        return str
    }

    make_filelist(): string {
        let itm = '<div id="dpx-tb-flist">'+
                '<button type="button" class="bk-bs-btn bk-bs-btn-default"'+
                ' id="dpx-tb-flist-btn">'+
                    '<span class="bk-bs-caret"/>'+
                '</button>'+
                '<div id="dpx-tb-flist-menu"><table>'
        if(this.model.filelist.length > 0)
            for(let j = 0; j < this.model.filelist.length; ++j) {
                itm += '<tr><td><label class="bk-bs-radio"><input'
                if(j == this.model.currentfile)
                    itm += ' checked=true'
                itm += ` type='radio' id='dpx-tb-flist-${j}' class='dpx-tb-flist-itm'/>`+
                       this.model.filelist[j]+"</label></td>"+
                       "<td><button type='button' class='bk-bs-btn bk-bs-btn-danger' "+
                       `id='dpx-tb-flist-btn-${j}' class='dpx-tb-flist-itm'>`+
                       this._icon('bin')+"</button></td>"+
                       "</tr>"
            }

        itm += '</table></div></div>'
        return itm
    }

    on_click_del_file(evt: MouseEvent): void {
        evt.preventDefault()
        evt.stopPropagation()

        const tmp          = evt.target.id.split('-')
        this.model.delfile = Number(tmp[tmp.length-1])
    }

    on_click_file(evt: MouseEvent): void {
        evt.preventDefault()
        evt.stopPropagation()

        tmp = evt.target.id.split('-')
        id  = Number(tmp[tmp.length-1])
        if(id == this.model.currentfile)
            return

        jQuery(this.el).find("#dpx-tb-flist-"+this.model.currentfile).prop('checked', false)
        jQuery(this.el).find("#dpx-tb-flist-"+id).prop('checked', true)
        this.model.currentfile = Number(id)
    }

    _icon(label:string) : string { return '<i class="icon-dpx-'+label+'"></i>' }

    render(): void {
        super.render()
        const mdl:  DpxToolbar = this.model
        let   quit: string     = ''
        let   docu: string     = ""
        if(this.model.hasquit)
            quit = `<div class='dpx-col-12'>${this.make_btn('quit', 'Quit', '', '')}</div>`
        if(this.model.hasdoc)
            docu = "<button type='button' id='dpx-tb-doc"+
                   "class='bk-bs-btn bk-bs-btn-default'>?</button>"

        const ttips: string[] = [
            'Open an analysis, i.e. ".ana" extension, or a track file and then its ".gr" files',
            'Select opened files',
            'Save an analysis, i.e. ".ana" extension, or create an xlsx report',
            'Change wether to discard (=) or select (≠) specific beads',
            'Remove the current bead'
        ]

        const html = this.make_btn('open', this._icon('folder-download'), ttips[0], '')+
               this.make_filelist()+
               this.make_btn('save', this._icon('folder-upload'), ttips[2])+
               "<label>Bead</label>"+
               "<input id='dpx-tb-bead'"+
               " class='dpx-freeze bk-widget-form-input'"+
               ` type='number' min=0  max=10000 step=1  value=${mdl.bead}>`+
               "<label>Discarded</label>"+
               this.make_btn('selection', '=', ttips[3])+
               "<input id='dpx-tb-discard'"+
                   " class='dpx-freeze bk-widget-form-input'"+
                   ` type='text' value='${mdl.discarded}'`+
                   ` placeholder='${mdl.helpmessage}'>`+
               this.make_btn('del', this._icon('bin'), ttips[4])+
               "<div id='dpx-tb-message' class='bk-markup'>"+
                   `${mdl.message}</div>`+ docu + quit

        const elem = jQuery(this.el)
        elem.html(html)
        elem.find('#dpx-tb-open').click(() => this.model.open = this.model.open+1)
        elem.find('#dpx-tb-save').click(() => this.model.save = this.model.save+1)
        elem.find('#dpx-tb-quit').click(() => this.model.quit = this.model.quit+1)
        elem.find('#dpx-tb-doc').click(() => this.model.doc = this.model.doc+1)
        elem.find('#dpx-tb-del') .click(() => this.on_discard_current())
        elem.find('#dpx-tb-bead').change(() => this.on_bead())
        elem.find('#dpx-tb-discard').change(() => this.on_discard())
        elem.find('#dpx-tb-selection').click(() => this.on_selection())
        if(this.model.filelist.length > 0)
            for(let i = 0; i < this.model.filelist.length; ++i){
                elem.find(`#dpx-tb-flist-${i}`).change((e) => this.on_click_file(e))
                elem.find(`#dpx-tb-flist-btn-${i}`).click((e) => this.on_click_del_file(e))
            }

        this.on_change_frozen()
    }
    get_width_height(): [number, number] {
        const width = super.get_width_height()[0]
        return [width, 30]
    }

    get_height() : number { return 30 }

    static initClass(): void {
        this.prototype.tagName = "div"

    }
}
DpxToolbarView.initClass()

export namespace DpxToolbar {
    export type Attrs = p.AttrsOf<Props>

    export type Props = WidgetView.Props & {
        frozen:      p.Property<boolean>
        open:        p.Property<number>
        currentfile: p.Property<number>
        delfile:     p.Property<number>
        filelist:    p.Property<string[]>
        save:        p.Property<number>
        doc:         p.Property<number>
        quit:        p.Property<number>
        bead:        p.Property<number>
        discarded:   p.Property<string>
        accepted:    p.Property<string>
        currentbead: p.Property<boolean>
        seltype:     p.Property<boolean>
        message:     p.Property<string>
        helpmessage: p.Property<string>
        hasquit:     p.Property<boolean>
        hasdoc:      p.Property<boolean>
    }
}

export interface DpxToolbar extends DpxToolbar.Attrs {}

export class DpxToolbar extends Widget {
    static initClass(): void {
        this.prototype.type = 'DpxToolbar'
        this.prototype.default_view = DpxToolbarView
        this.override({
            css_classes: ["dpx-row", "dpx-widget", "dpx-tb", "dpx-span"]
        })
        this.define({
            frozen:      [p.Bool,    true],
            open:        [p.Number,  0],
            currentfile: [p.Number,  -1],
            delfile:     [p.Number,  -1],
            filelist:    [p.Array,   []],
            save:        [p.Number,  0],
            doc:         [p.Number,  0],
            quit:        [p.Number,  0],
            bead:        [p.Number,  -1],
            discarded:   [p.String,  ''],
            accepted:    [p.String,  ''],
            currentbead: [p.Bool,    true],
            seltype:     [p.Bool,    true],
            message:     [p.String,  ''],
            helpmessage: [p.String, ''],
            hasquit:     [p.Bool,    false],
            hasdoc:     [p.Bool,    false]
        })
    }
}
DpxToolbar.initClass()
