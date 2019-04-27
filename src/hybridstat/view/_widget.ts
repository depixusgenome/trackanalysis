import * as p               from "core/properties"
import {WidgetView, Widget} from "models/widgets/widget"

declare function jQuery(...args: any[]): any

export class DpxFitParamsView extends WidgetView {
    model: DpxFitParams
    cl_inputs: string[]
    _set_lock(): void {
        const elem = jQuery(this.el).find("#dpx-pk-ls-icon")
        elem.removeClass()
        if (this.model.locksequence)
            elem.addClass("icon-dpx-lock")
        else
            elem.addClass("icon-dpx-unlocked")
    }

    on_lock(): void {
        this.model.locksequence = !this.model.locksequence
        this._set_lock()
    }

    on_input(evt: Event): void {
        let t = evt.target as any as {id: string, value:string}
        this.model[t.id.slice(7)] = t.value
    }

    on_change_input(evt: string): void {
        let itm = jQuery(this.el).find(`#dpx-pk-${evt}`)
        if (evt == 'locksequence')
            this._set_lock()
        else
            itm.val(`${this.model[evt]}`)
    }

    connect_signals(): void {
        super.connect_signals()
        for(let evt of this.cl_inputs)
            this.connect(
                this.model.properties[evt].change,
                ((e:string) => (() => this.on_change_input(e)))(evt)
            )
        this.connect(this.model.properties.frozen.change, () => this.render())
    }

    render(): void {
        super.render()
        const dbal  : string   =  'data-balloon="'
        const pos   : string   = '" data-balloon-length="medium" data-balloon-pos="right"'
        const ttips : string[] = [
            dbal+'Force a stretch value (base/µm)'+pos,
            dbal+'Force a bias value (µm)'+pos,
            dbal+'Lock the sequence to the currently selected one'+pos
        ]

                

        this.el.innerHTML = "<div class='dpx-span'>"+
            this.mk_inp("stretch", "Stretch", ttips[0])+
            this.mk_inp("bias",    "Bias (µm)", ttips[1])+
            this.mk_check(ttips[2])+
            "</div>"

        const elem = jQuery(this.el)
        for(let evt of ["stretch", "bias"])
            elem.find(`#dpx-pk-${evt}`).change((e:Event) => this.on_input(e))
        elem.find("#dpx-pk-locksequence").click(() => this.on_lock())
    }

    mk_inp(name: string, label: string, ttip: string): string {
        const disabled = this.model.frozen ? ' disabled=true' : ''
        return  `<input id='dpx-pk-${name}' ${ttip}`+
            ` class='dpx-fp-freeze bk-widget-form-input' type='text' `+
            ` placeholder='${label}' value='${this.model[name]}'${disabled}>`
    }

    mk_check(ttip: string): string {
        const disabled = this.model.frozen ? ' disabled=true' : ''
        const icon     = this.model.locksequence ? 'lock' : 'unlocked'
        return `<button type='button' id='dpx-pk-locksequence' ${ttip} `+
            `class='dpx-fp-freeze bk-bs-btn bk-bs-btn-default'${disabled}>`+
            `<span class='icon-dpx-${icon}'${disabled} `+
            `id='dpx-pk-ls-icon'>Hairpin</span></button>`
    }

    static initClass() : void {
        this.prototype.tagName   = "div"
        this.prototype.cl_inputs = ["stretch", "bias", "locksequence"]
    }
}
DpxFitParamsView.initClass()

export namespace DpxFitParams {
    export type Attrs = p.AttrsOf<Props>

    export type Props = Widget.Props & {
        frozen:        p.Property<boolean>
        stretch:       p.Property<string>
        bias:          p.Property<string>
        locksequence:  p.Property<boolean>
        [key: string]: p.Property<any>
    }
}

export interface DpxFitParams extends DpxFitParams.Attrs {}

export class DpxFitParams extends Widget {
    properties: DpxFitParams.Props
    constructor(attrs?: Partial<DpxFitParams.Attrs>) { super(attrs); }
    static initClass(): void {
        this.prototype.default_view= DpxFitParamsView
        this.prototype.type=         "DpxFitParams"
        this.override({css_classes: ["dpx-params", "dpx-widget"]})
        this.define<DpxFitParams.Props>({
            frozen:       [p.Boolean, true],
            stretch:      [p.String, ""],
            bias:         [p.String, ""],
            locksequence: [p.Boolean]
        })
    }
}
DpxFitParams.initClass()
