import {Div, DivView} from "models/widgets/div"
import * as p from "core/properties"

export namespace PeaksStatsDiv {
    export type Attrs = p.AttrsOf<Props>

    export type Props = Div.Props & {
        data: p.Property<any>
    }
}

export interface PeaksStatsDiv extends PeaksStatsDiv.Attrs {}

export class PeaksStatsDiv extends Div {
    properties: PeaksStatsDiv.Props
    constructor(attrs?: Partial<PeaksStatsDiv.Attrs>) { super(attrs); }

    static initClass() : void {
        this.prototype.type= "PeaksStatsDiv"
        this.prototype.default_view= DivView
        this.define<PeaksStatsDiv.Props>({ data: [ p.Any,  {}] })
    }
}
PeaksStatsDiv.initClass()
