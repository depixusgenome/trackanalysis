import * as DOM from "core/util/dom";

interface IntInputProps {
  id: string;
  title: string;
  name: string;
  value: float;
  start: float;
  step: float;
  end: float;
}

export default (props: IntInputProps): HTMLElement => {
  return (
    <fragment>
    <table class="dpx-int-input" style="margin-right: 5px; margin-top: 9px; margin-left: 5px">
    <tr><td><label for={props.id}>{props.title}</label></td>
        <td><input class="bk-widget-form-input" type="number"
            id={props.id} name={props.name} value={props.value} 
            min={props.start} max={props.end}
            step={props.step}/>
        </td></tr></table>
    </fragment>
  )
}
