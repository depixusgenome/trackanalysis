import * as p               from "core/properties"
import {AutocompleteInputView, AutocompleteInput} from "models/widgets/autocomplete_input"

export class DpxAutocompleteInputView extends AutocompleteInputView {
    model: AutocompleteInput
    change_input(): void {
        var val:string = this.input_el.value;
        if(this._open && this._hover_index >= 0 && this.menu.children.length > this._hover_index)
        {
            var tmp = this.menu.children[this._hover_index].textContent
            if(tmp != null)
                val = tmp;
        }
        this.model.value = val;
        this.input_el.focus();
        if (this._open)
            this._hide_menu();
    };
}

export namespace DpxAutocompleteInput {
    export type Attrs = p.AttrsOf<Props>
    export type Props = AutocompleteInput.Props
}

export interface DpxAutocompleteInput extends DpxAutocompleteInput.Attrs {}

export class DpxAutocompleteInput extends AutocompleteInput {
    properties: DpxAutocompleteInput.Props
    constructor(attrs?: Partial<DpxAutocompleteInput.Attrs>) { super(attrs); }
    static initClass(): void {
        this.prototype.type = "DpxAutocompleteInput"
        this.prototype.default_view= DpxAutocompleteInputView
    }
}
DpxAutocompleteInput.initClass()
