/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { BookOpen, Map } from "lucide-react";
// ui
import { Tooltip } from "@plane/propel/tooltip";
// hooks
import { usePlatformOS } from "@/hooks/use-platform-os";
import { AGENTPM_DOCS_URL, AGENTPM_ROADMAP_URL } from "@/constants/agentpm";
import packageJson from "package.json";

export const WorkspaceEditionBadge = observer(function WorkspaceEditionBadge() {
  // platform
  const { isMobile } = usePlatformOS();

  return (
    <Tooltip tooltipContent={`Version: v${packageJson.version}`} isMobile={isMobile}>
      <div className="flex items-center gap-1">
        <a
          className="flex h-8 items-center gap-1 rounded px-2 text-12 font-medium text-secondary hover:bg-surface-2 hover:text-primary"
          href={AGENTPM_ROADMAP_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Map className="size-3.5" />
          Roadmap
        </a>
        <a
          className="flex h-8 items-center gap-1 rounded px-2 text-12 font-medium text-secondary hover:bg-surface-2 hover:text-primary"
          href={AGENTPM_DOCS_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          <BookOpen className="size-3.5" />
          Docs
        </a>
      </div>
    </Tooltip>
  );
});
