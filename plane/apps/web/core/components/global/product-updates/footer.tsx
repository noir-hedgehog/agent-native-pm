/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { USER_TRACKER_ELEMENTS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { GithubIcon } from "lucide-react";
// ui
import { getButtonStyling } from "@plane/propel/button";
// helpers
import { cn } from "@plane/utils";
import { AGENTPM_DOCS_URL, AGENTPM_GITHUB_URL, AGENTPM_NEW_ISSUE_URL, AGENTPM_ROADMAP_URL } from "@/constants/agentpm";

export function ProductUpdatesFooter() {
  const { t } = useTranslation();
  return (
    <div className="m-6 mb-4 flex flex-shrink-0 items-center justify-between gap-4">
      <div className="flex items-center gap-2">
        <a
          href={AGENTPM_DOCS_URL}
          target="_blank"
          className="text-13 text-secondary underline-offset-1 outline-none hover:text-primary hover:underline"
          rel="noreferrer"
        >
          {t("docs")}
        </a>
        <svg viewBox="0 0 2 2" className="h-0.5 w-0.5 fill-current">
          <circle cx={1} cy={1} r={1} />
        </svg>
        <a
          data-ph-element={USER_TRACKER_ELEMENTS.CHANGELOG_REDIRECTED}
          href={AGENTPM_ROADMAP_URL}
          target="_blank"
          className="text-13 text-secondary underline-offset-1 outline-none hover:text-primary hover:underline"
          rel="noreferrer"
        >
          Roadmap
        </a>
        <svg viewBox="0 0 2 2" className="h-0.5 w-0.5 fill-current">
          <circle cx={1} cy={1} r={1} />
        </svg>
        <a
          href={AGENTPM_NEW_ISSUE_URL}
          target="_blank"
          className="text-13 text-secondary underline-offset-1 outline-none hover:text-primary hover:underline"
          rel="noreferrer"
        >
          Issues
        </a>
        <svg viewBox="0 0 2 2" className="h-0.5 w-0.5 fill-current">
          <circle cx={1} cy={1} r={1} />
        </svg>
        <a
          href={AGENTPM_ROADMAP_URL}
          target="_blank"
          className="text-13 text-secondary underline-offset-1 outline-none hover:text-primary hover:underline"
          rel="noreferrer"
        >
          Roadmap
        </a>
      </div>
      <a
        href={AGENTPM_GITHUB_URL}
        target="_blank"
        className={cn(
          getButtonStyling("secondary", "base"),
          "flex items-center gap-1.5 text-center font-medium underline-offset-2 outline-none hover:underline"
        )}
        rel="noreferrer"
      >
        <GithubIcon className="h-4 w-auto text-primary" />
        AgentPM
      </a>
    </div>
  );
}
