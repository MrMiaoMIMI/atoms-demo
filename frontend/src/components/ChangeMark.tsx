import type { ChangeFile, ChangeType } from "../types";

export const CHANGE_LABEL: Record<ChangeType, string> = {
  created: "新增",
  modified: "修改",
  deleted: "删除",
};

/** Compact marker shared by the file tree, the diff tree and the filters. */
export const CHANGE_SHORT: Record<ChangeType, string> = {
  created: "增",
  modified: "改",
  deleted: "删",
};

export const CHANGE_TEXT_CLASS: Record<ChangeType, string> = {
  created: "text-[#15803d]",
  modified: "text-[#b45309]",
  deleted: "text-[#b91c1c]",
};

export default function ChangeMark({ change }: { change: ChangeFile }) {
  return (
    <span
      title={`${CHANGE_LABEL[change.change_type]} +${change.additions} −${change.deletions}`}
      className={`flex-none text-[10.5px] font-medium leading-none ${
        CHANGE_TEXT_CLASS[change.change_type]
      }`}
    >
      {CHANGE_SHORT[change.change_type]}
    </span>
  );
}
