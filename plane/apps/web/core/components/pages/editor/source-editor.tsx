/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { Braces, FileText, Pilcrow } from "lucide-react";
import { observer } from "mobx-react";
import { cn } from "@plane/utils";
import type { TPageInstance } from "@/store/pages/base-page";
import { PageEditorHeaderRoot } from "./header";

const FORMATS = [
  { value: "rich_text", label: "Rich text", icon: Pilcrow },
  { value: "markdown", label: "Markdown", icon: FileText },
  { value: "yaml", label: "YAML", icon: Braces },
] as const;

type Props = {
  page: TPageInstance;
  projectId?: string;
};

export const PageSourceEditor = observer(function PageSourceEditor({ page, projectId }: Props) {
  const [source, setSource] = useState(page.source_text);

  useEffect(() => setSource(page.source_text), [page.id, page.source_text]);

  useEffect(() => {
    if (source === page.source_text || page.source_format === "rich_text") return;
    const timeout = window.setTimeout(() => {
      void page.updateDescription({
        description_binary: "",
        description_html: page.description_html ?? "<p></p>",
        description_json: page.description_json ?? {},
        source_format: page.source_format,
        source_text: source,
      });
    }, 800);
    return () => window.clearTimeout(timeout);
  }, [page, source]);

  return (
    <div className="vertical-scrollbar size-full overflow-y-auto">
      <div className="mx-auto w-full max-w-[960px] px-page-x pb-32">
        <PageEditorHeaderRoot page={page} projectId={projectId} />
        <textarea
          aria-label={`${page.source_format} page source`}
          className="min-h-[60vh] w-full resize-y border-0 bg-transparent p-3 font-mono text-13 leading-6 text-primary outline-none placeholder:text-placeholder"
          value={source}
          readOnly={!page.isContentEditable}
          spellCheck={page.source_format === "markdown"}
          onChange={(event) => setSource(event.target.value)}
        />
      </div>
    </div>
  );
});

export const PageSourceFormatSwitcher = observer(function PageSourceFormatSwitcher({
  page,
}: Pick<Props, "page">) {
  const changeFormat = (sourceFormat: (typeof FORMATS)[number]["value"]) => {
    if (sourceFormat === page.source_format) return;
    void page.updateDescription({
      description_binary: "",
      description_html: page.description_html ?? "<p></p>",
      description_json: page.description_json ?? {},
      source_format: sourceFormat,
      source_text: page.source_text,
    });
  };

  return (
    <div className="flex shrink-0 items-center justify-end border-b border-subtle bg-surface-1 px-3">
      {FORMATS.map((format) => {
        const Icon = format.icon;
        return (
          <button
            key={format.value}
            type="button"
            disabled={!page.isContentEditable}
            onClick={() => changeFormat(format.value)}
            className={cn(
              "flex h-8 items-center gap-1.5 border-b-2 px-3 text-12 text-secondary",
              page.source_format === format.value
                ? "border-accent-strong text-primary"
                : "border-transparent hover:text-primary",
            )}
          >
            <Icon className="size-3.5" />
            {format.label}
          </button>
        );
      })}
    </div>
  );
});
