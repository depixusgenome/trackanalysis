import {Div, DivView} from "models/widgets/div"
import * as p from "core/properties"

export class PeaksStatsDiv extends Div
    type: "PeaksStatsDiv"
    default_view: DivView

    @define { data: [ p.Any,  {}] }
