import * as DOM from "core/util/dom";

interface IntInputProps {
  id: string;
  title: string;
  name: string;
  value: float;
  minvalue: float;
  maxvalue: float;
}

export default (props: IntInputProps): HTMLElement => {
  return (
    <fragment>
      <label for={props.id}>{props.title}</label>
      <input class="bk-widget-form-input" type="number"
        id={props.id} name={props.name} value={props.value} 
        min="{props.minvalue}" max="{props.maxvalue}"/>
    </fragment>
  )
}
