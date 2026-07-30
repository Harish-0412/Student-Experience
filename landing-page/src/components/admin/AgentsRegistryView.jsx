import React from 'react';
import { useApp } from '../../context/AppContext';
import { Cpu } from 'lucide-react';

export const AgentsRegistryView = () => {
  const { agents } = useApp();

  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <div>
        <h1 className="flex items-center gap-3 text-3xl font-extrabold text-white">
          <Cpu className="h-8 w-8 text-purple-400" />
          Implemented Agent Registry
        </h1>
        <p className="mt-2 text-sm text-gray-400">
          {agents.length} descriptors returned by the Phase 1-4 backend.
        </p>
      </div>

      <div className="overflow-x-auto border-y border-white/10">
        <table className="w-full min-w-[980px] text-left text-sm text-gray-300">
          <thead className="border-b border-white/10 text-xs uppercase text-gray-500">
            <tr>
              <th className="p-4">Agent</th>
              <th className="p-4">Phase</th>
              <th className="p-4">Version</th>
              <th className="p-4">Allowed tools</th>
              <th className="p-4">Model route</th>
              <th className="p-4">Runs</th>
              <th className="p-4">Latest status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {agents.map((agent) => (
              <tr key={`${agent.phase}-${agent.name}`}>
                <td className="p-4 font-bold text-white">{agent.name}</td>
                <td className="p-4 text-xs text-purple-300">{agent.phase}</td>
                <td className="p-4 font-mono text-xs">{agent.version}</td>
                <td className="p-4 text-xs text-gray-400">
                  {agent.allowed_tools.join(', ') || 'No tools declared'}
                </td>
                <td className="p-4 font-mono text-xs text-gray-400">
                  {agent.model_route || 'Internal deterministic route'}
                </td>
                <td className="p-4">{agent.runCount}</td>
                <td className="p-4">
                  <span className="text-xs font-bold uppercase text-emerald-300">
                    {agent.lastStatus.replaceAll('_', ' ')}
                  </span>
                  {agent.lastRunAt && (
                    <span className="mt-1 block text-[10px] text-gray-500">
                      {new Date(agent.lastRunAt).toLocaleString()}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
