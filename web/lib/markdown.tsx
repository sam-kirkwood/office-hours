import Markdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

interface Props {
  source: string;
  className?: string;
}

export default function MarkdownLatex({ source, className }: Props) {
  return (
    <div className={className}>
      <Markdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
      >
        {source}
      </Markdown>
    </div>
  );
}
