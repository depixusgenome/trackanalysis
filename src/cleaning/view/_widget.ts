import *        as p    from "core/properties"
import {WidgetView, Widget} from "models/widgets/widget"

declare function jQuery(...args: any[]): any

export class DpxCleaningView extends WidgetView {
    model: DpxCleaning
    cl_inputs: string[]

    mk_inp(name: string): string {
        const val  = this.model[name]
        const dv   = Math.pow(10, Math.log10(val)-1)
        const maxv = Math.pow(10, Math.log10(val)+2)
        return this.mk_inp_with_extrema(name, maxv, dv)
    }

    mk_inp_with_extrema(name:string, maxv:number, dv:number): string {
        const disabled = this.model.frozen ? ' disabled=true' : ''
        return  `<input id='dpx-cl-${name}'`+
            ` class='dpx-cl-freeze bk bk-input'`+
            ` type='number' min=0 max=${maxv} step=${dv} `+
            ` value=${this.model[name]}${disabled}>`
    }

    mk_txt(name:string, placeholder:string = '') : string {
        const disabled = this.model.frozen ? ' disabled=true' : ''
        return  `<input id='dpx-cl-${name}'`+
            ` type='text' class='dpx-cl-freeze bk bk-input'`+
            ` value='${this.model[name]}'${disabled}`+
            ` placeholder='${placeholder}'>`
    }

    mk_btn(name:string, label:string, ttip: string): string {
        const disabled = this.model.frozen ? ' disabled=true' : ''
        return `<button type='button' id='dpx-cl-${name}' ${ttip} `+
            `class='dpx-cl-freeze bk bk-btn bk-btn-default'${disabled}>`+
            label+"</button>"
    }

    on_change_frozen(): void {
        jQuery(this.el).find('.dpx-cl-freeze').prop('disabled', this.model.frozen)
    }

    on_input(evt:string): void {
        this.model[evt] = Number(jQuery(this.el).find(`#dpx-cl-${evt}`).val())
    }

    on_change_input(evt:string) : void {
        jQuery(this.el).find(`#dpx-cl-${evt}`).val(`${this.model[evt]}`)
    }

    connect_signals(): void {
        super.connect_signals()
        this.connect(
            this.model.properties.subtracted.change,
            () => jQuery(this.el).find("#dpx-cl-subtracted").val(`${this.model.subtracted}`))
        for(let evt of this.cl_inputs)
            this.connect(
                this.model.properties[evt].change,
                ((e:string) => (() => this.on_change_input(e)))(evt)
            )
        this.connect(this.model.properties.frozen.change, () => this.on_change_frozen())
        this.connect(this.model.properties.fixedbeads.change, () => this.render())
    }

    render(): void {
        super.render()
        const dbal  = 'aria-label="'
        const pos   = '" data-balloon-length="medium" data-balloon-pos="right"'
        let   ttips = [
            dbal+'Average of listed bead is subtracted from other beads'+pos,
            dbal+'Adds the current bead to the list'+pos,
            dbal+'Values too far are deleted '+pos,
            dbal+'Cycles with a range of values to small or too big are deleted'+pos,
            dbal+'Values with a high derivate are deleted'+pos,
            dbal+'Underpopulated cycles are deleted'+pos,
            dbal+'Constant or noisy cycles are deleted'+pos,
            dbal+'Enough cycles should reach 0 or the bead is discarded'+pos
        ]

        this.el.innerHTML = ""+
            "<table>"+
                "<tr><td>Fixed beads</td>"+
                    "<td id='dpx-cl-fixedbeads' style='width:350px;'>"+
                        this.model.fixedbeads+"</td></tr>"+
               `<tr><td ${ttips[0]}>Subtracted</td>`+
                   `<td><div  class='dpx-span'>${this.mk_txt(`subtracted`)}`+
                        `${this.mk_btn(`add`, `╋`, ttips[1])}</div></td></tr>`+
            "</table>"+
            "<table>"+
                `<tr><td ${ttips[2]}>|z| ≤</td>`+
                    `<td>${this.mk_inp(`maxabsvalue`)}</td>`+
                    `<td ${ttips[4]}>|dz/dt| ≤</td>`+
                    `<td>${this.mk_inp(`maxderivate`)}</td></tr>`+
                `<tr><td></td>`+
                     `<td>${this.mk_inp(`minextent`)}</td>`+
                     `<td ${ttips[3]}>≤ Δz ≤</td>`+
                     `<td>${this.mk_inp(`maxextent`)}</td></tr>`+
                 `<tr><td></td>`+
                     `<td>${this.mk_inp(`minhfsigma`)}</td>`+
                     `<td ${ttips[6]}>≤ σ[HF] ≤</td>`+
                     `<td>${this.mk_inp(`maxhfsigma`)}</td></tr>`+
                 `<tr><td ${ttips[5]}>% good  ≥</td>`+
                     `<td>${this.mk_inp_with_extrema(`minpopulation`, 100, 0.1)}</td>`+
                     `<td ${ttips[7]}>Non-closing cycles (%)</td>`+
                     `<td>${this.mk_inp_with_extrema(`maxsaturation`, 100.0, 1.0)}</td></tr>`+
             "</table>"

        const elem = jQuery(this.el)
        elem.find("#dpx-cl-subtracted").change((e:Event) => {
            this.model.subtracted = (e.target as any).value
        })
        elem.find("#dpx-cl-add").click(
            () => this.model.subtractcurrent =  this.model.subtractcurrent+1
        )
        for(let evt of this.cl_inputs) {
            let el = elem.find(`#dpx-cl-${evt}`)
            el.change((e:Event) => {
                let t = e.target as any as {value: string, id: string}
                this.model[t.id.slice(7)] = Number(t.value)
            })
        }
    }

    static initClass(): void {
        this.prototype.tagName = "div"
        this.prototype.cl_inputs = [
            'maxabsvalue', 'maxderivate', 'minpopulation', 'minhfsigma',
            'maxhfsigma', 'minextent', 'maxextent', 'maxsaturation'
        ]
    }
}
DpxCleaningView.initClass()

export namespace DpxCleaning {
    export type Attrs = p.AttrsOf<Props>
    export type Props = Widget.Props & {
        frozen:          p.Property<boolean>
        framerate:       p.Property<number>
        figure:          p.Property<any>
        fixedbeads:      p.Property<string>
        subtracted:      p.Property<string>
        subtractcurrent: p.Property<number>
        maxabsvalue:     p.Property<number>
        maxderivate:     p.Property<number>
        minpopulation:   p.Property<number>
        minhfsigma:      p.Property<number>
        maxhfsigma:      p.Property<number>
        minextent:       p.Property<number>
        maxextent:       p.Property<number>
        maxsaturation:   p.Property<number>
        [key: string]:   p.Property<any>
    }
}

export interface DpxCleaning extends DpxCleaning.Attrs 
{
    [key: string] : any
}

export class DpxCleaning extends Widget {
    properties: DpxCleaning.Props
    constructor(attrs?: Partial<DpxCleaning.Attrs>) {
        super(attrs);
    }

    onchangebounds() {
        let trng         = this.figure.extra_x_ranges['time']
        let xrng         = this.figure.x_range
        trng.reset_start = xrng.reset_start/this.framerate
        trng.reset_end   = xrng.reset_end/this.framerate
        trng.start       = xrng.start/this.framerate
        trng.end         = xrng.end  /this.framerate
    }

    static initClass(): void {
        this.prototype.default_view = DpxCleaningView
        this.prototype.type =         "DpxCleaning"

        this.override({
            css_classes : ["dpx-cleaning", "dpx-widget"]
        })
        this.define<DpxCleaning.Props>({
            frozen:          [p.Boolean, true],
            framerate:       [p.Number, 30],
            figure:          [p.Instance],
            fixedbeads:      [p.String, ""],
            subtracted:      [p.String, ""],
            subtractcurrent: [p.Number, 0],
            maxabsvalue:     [p.Number, 5],
            maxderivate:     [p.Number, 2],
            minpopulation:   [p.Number, 80],
            minhfsigma:      [p.Number, 1e-4],
            maxhfsigma:      [p.Number, 1e-2],
            minextent:       [p.Number, .25],
            maxextent:       [p.Number, 2.0],
            maxsaturation:   [p.Number, 20],
        })
    }
}
DpxCleaning.initClass()
