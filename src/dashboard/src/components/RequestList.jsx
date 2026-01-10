import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchRequests, createRequest } from '../api/client';

const STATUS_COLORS = {
    pending: 'bg-yellow-100 text-yellow-800',
    searching: 'bg-blue-100 text-blue-800',
    processing_search: 'bg-blue-200 text-blue-900',
    analyzing: 'bg-purple-100 text-purple-800',
    processing_analysis: 'bg-purple-200 text-purple-900',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
};

function RequestList() {
    const [requests, setRequests] = useState([]);
    const [filter, setFilter] = useState('all');
    const [loading, setLoading] = useState(true);
    const [newTopic, setNewTopic] = useState('');
    const [creating, setCreating] = useState(false);

    const loadRequests = async () => {
        try {
            const data = await fetchRequests(filter);
            setRequests(data.items);
        } catch (error) {
            console.error('Failed to load requests:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadRequests();
        const interval = setInterval(loadRequests, 5000); // Auto-refresh every 5s
        return () => clearInterval(interval);
    }, [filter]);

    const handleCreateRequest = async (e) => {
        e.preventDefault();
        if (!newTopic.trim()) return;

        setCreating(true);
        try {
            await createRequest(newTopic);
            setNewTopic('');
            await loadRequests();
        } catch (error) {
            console.error('Failed to create request:', error);
        } finally {
            setCreating(false);
        }
    };

    if (loading) {
        return <div className="text-center py-8">Loading...</div>;
    }

    return (
        <div>
            {/* Header with Create Form */}
            <div className="bg-white shadow rounded-lg p-6 mb-6">
                <h2 className="text-2xl font-bold mb-4">Create New Analysis</h2>
                <form onSubmit={handleCreateRequest} className="flex gap-4">
                    <input
                        type="text"
                        value={newTopic}
                        onChange={(e) => setNewTopic(e.target.value)}
                        placeholder="Enter topic to analyze..."
                        className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        disabled={creating}
                    />
                    <button
                        type="submit"
                        disabled={creating || !newTopic.trim()}
                        className="px-6 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                    >
                        {creating ? 'Creating...' : 'Analyze'}
                    </button>
                </form>
            </div>

            {/* Filters */}
            <div className="bg-white shadow rounded-lg p-4 mb-6">
                <div className="flex gap-2">
                    {['all', 'completed', 'analyzing', 'searching', 'failed'].map((status) => (
                        <button
                            key={status}
                            onClick={() => setFilter(status)}
                            className={`px-4 py-2 rounded-md font-medium ${filter === status
                                    ? 'bg-indigo-600 text-white'
                                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                        >
                            {status.charAt(0).toUpperCase() + status.slice(1)}
                        </button>
                    ))}
                </div>
            </div>

            {/* Request List */}
            <div className="bg-white shadow rounded-lg overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Topic
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Status
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Results
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Created
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Actions
                            </th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {requests.map((request) => (
                            <tr key={request.request_id} className="hover:bg-gray-50">
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <div className="text-sm font-medium text-gray-900">{request.topic}</div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${STATUS_COLORS[request.status]}`}>
                                        {request.status}
                                    </span>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                    {request.search_results_count} results
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                    {new Date(request.created_at).toLocaleString()}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                    <Link to={`/requests/${request.request_id}`} className="text-indigo-600 hover:text-indigo-900">
                                        View Details
                                    </Link>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>

                {requests.length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                        No requests found. Create one above!
                    </div>
                )}
            </div>
        </div>
    );
}

export default RequestList;
