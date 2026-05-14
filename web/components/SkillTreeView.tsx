"use client";

import dynamic from "next/dynamic";
import type { ComponentProps } from "react";
import type SkillTree from "./SkillTree";

const SkillTreeDynamic = dynamic(() => import("./SkillTree"), { ssr: false });

export default function SkillTreeView(props: ComponentProps<typeof SkillTree>) {
  return <SkillTreeDynamic {...props} />;
}
