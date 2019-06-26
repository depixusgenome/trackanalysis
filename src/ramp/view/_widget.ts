import *        as p        from "core/properties"
import {WidgetView, Widget} from "models/widgets/widget"

declare function jQuery(...args: any[]): any

export class DpxRampView extends WidgetView {
    model: DpxRamp
    cl_inputs: string[]
    on_change_frozen() {
        jQuery(this.el).find('.dpx-rp-freeze').prop('disabled', this.model.frozen)
    }

    on_input(evt:string) {
        this.model[evt] = Number(jQuery(this.el).find("#dpx-rp-"+evt).val())
    }

    on_change_input(evt:string) {
        jQuery(this.el).find("#dpx-rp-"+evt).val(this.model[evt])
    }

    connect_signals() {
        super.connect_signals()
        for(let evt of this.cl_inputs)
            this.connect(
                this.model.properties[evt].change,
                ((e:string) => { return (): void => { this.on_change_input(e) } })(evt)
            )
        this.connect(this.model.properties.displaytype.change,  (): void => this.render())
        this.connect(this.model.properties.frozen.change, (): void => this.on_change_frozen())
    }

    render(): void {
        super.render()
        let dbal: string = 'data-balloon="'
        let pos:  string = '" data-balloon-length="medium" data-balloon-pos="right"'
        let ttips: string[] = [
            dbal+'beads with a small range of values are defined as fixed'+pos,
            dbal+'Beads with a range of values to small or too big are deleted'+pos,
            dbal+'Constant or noisy beads are deleted'+pos,
            dbal+'Normalize all bead sizes to 1.'+pos
        ]

        let html: string  = (
            `<table>
                <tr><td>${this.mk_inp('minhfsigma', 0.05, 0.0001)}</td>
                    <td ${ttips[2]}>≤ σ[HF] ≤</td>
                    <td>${this.mk_inp('maxhfsigma', 0.05,  0.001)}</td></tr>
                <tr><td>${this.mk_inp('minextension', 10.0, 0.05)}</td>
                    <td ${ttips[1]}>≤ Δz ≤</td>
                    <td>${this.mk_inp('maxextension', 10.0, 0.05)}</td></tr>
                <tr><td></td>
                    <td ${ttips[0]}>Δz fixed ≤</td>
                    <td>${this.mk_inp('fixedextension')}</td></tr>
             </table><div class='dpx-span'>
             <label class='bk-bs-radio' style='display: none !important;'>
             </label>`
        )

        let labels: string[] = ["raw data", "Z (% strand size)", "Z (µm)"]
        let disabled: string = this.model.frozen ? ' disabled=true' : ''
        for(let j = 0; j < 3; ++j) {
            html += `<label class='bk-bs-radio'><input ${disabled}
                ${j == this.model.displaytype ?' checked=true': ''}
                type='radio' id='dpx-rp-displaytype-${j}'
                class='dpx-rp-displaytype-itm dpx-rp-freeze'/>
                ${labels[j]}</label>`
        }
        html += "</div>"

        this.el.innerHTML = html

        let elem = jQuery(this.el)
        for(let j of this.cl_inputs) {
            let el = elem.find("#dpx-rp-"+j)
            el.change((e:Event) => {
                let t = e.target as any as {id: string, value: string}
                this.model[t.id.slice(7)] = Number(t.value)
            })
        }

        for(let j = 0; j < 3; ++ j)
            elem.find("#dpx-rp-displaytype-"+j).change((e:Event) => this.on_click_display(e))

    }

    on_click_display(evt: Event) : void {
        evt.preventDefault()
        evt.stopPropagation()

        let t   = evt.target as any as {id: string}
        let tmp = t.id.split('-')
        let id  = tmp[tmp.length-1]
        if(id == `${this.model.displaytype}`)
            return

        jQuery(this.el).find("#dpx-rp-displaytype-"+this.model.displaytype).prop('checked', false)
        jQuery(this.el).find("#dpx-rp-displaytype-"+id).prop('checked', true)
        this.model.displaytype = Number(id)
    }

    mk_inp(name: string, maxv:number = 100, dv: number = 0.1): string {
        return `<input id='dpx-rp-${name}'
             class='dpx-rp-freeze bk-widget-form-input'"
             type='number' min=0 max=${maxv} step=${dv}
             value=${this.model[name]}${this.model.frozen ? ' disabled=true' : ''}>`
    }

    static initClass() : void {
        this.prototype.tagName = "div"
        this.prototype.cl_inputs = ['minhfsigma', 'maxhfsigma', 'minextension', 'maxextension']
    }
}
DpxRampView.initClass()

export namespace DpxRamp {
    export type Attrs = p.AttrsOf<Props>
    export type Props = Widget.Props & {
        frozen:         p.Property<boolean>
        minhfsigma:     p.Property<number>
        maxhfsigma:     p.Property<number>
        minextension:   p.Property<number>
        fixedextension: p.Property<number>
        maxextension:   p.Property<number>
        displaytype:    p.Property<number>
        [key:string]:   p.Property<any>
    }
}

export interface DpxRamp extends DpxRamp.Attrs {}

export class DpxRamp extends Widget {
    properties: DpxRamp.Props
    constructor(attrs?: Partial<DpxRamp.Attrs>) { super(attrs) }

    static initClass() : void {
        this.prototype.default_view = DpxRampView
        this.prototype.type         = "DpxRamp"

        this.define<DpxRamp.Props>({
            frozen:         [p.Boolean, true],
            minhfsigma:     [p.Number,  1e-4],
            maxhfsigma:     [p.Number,  5e-3],
            minextension:   [p.Number,  .05],
            fixedextension: [p.Number,  .4],
            maxextension:   [p.Number,  1.5],
            displaytype:    [p.Number,  0]
        })
        this.override({css_classes: ["dpx-ramp", "dpx-widget"]})
    }
}
DpxRamp.initClass()
