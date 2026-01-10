import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchRequestDetail } from '../api/client';

const STATUS_COLORS = {
    pending: 'bg-yellow-100 text-yellow-800',
    searching: 'bg-blue-100 text-blue-800',
    processing_search: 'bg-blue-200 text-blue-900',
    analyzing: 'bg-purple-100 text-purple-800',
    processing_analysis: 'bg-purple-200 text-purple-900',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
};

function RequestDetail() {
    const { requestId } = useParams();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const loadData = async () => {
            try {
                const result = await fetchRequestDetail(requestId);
                setData(result);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        loadData();
        const interval = setInterval(loadData, 5000); // Auto-refresh
        return () => clearInterval(interval);
    }, [requestId]);

    if (loading) {
        return <div className="text-center py-8">Loading...</div>;
    }

    if (error) {
        return (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-red-800">Error: {error}</p>
                <Link to="/" className="text-indigo-600 hover:text-indigo-800 mt-2 inline-block">
                    ← Back to list
                </Link>
            </div>
        );
    }

    const { request, search_results, analysis_result } = data;

    return (
        <div>
            {/* Back Button */}
            <Link to="/" className="text-indigo-600 hover:text-indigo-800 mb-4 inline-block">
                ← Back to list
            </Link>

            {/* Request Info */}
            <div className="bg-white shadow rounded-lg p-6 mb-6">
                <div className="flex justify-between items-start mb-4">
                    <h2 className="text-2xl font-bold">{request.topic}</h2>
                    <span className={`px-3 py-1 text-sm font-semibold rounded-full ${STATUS_COLORS[request.status]}`}>
                        {request.status}
                    </span>
                </div>

                <dl className="grid grid-cols-2 gap-4">
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Request ID</dt>
                        <dd className="mt-1 text-sm text-gray-900 font-mono">{request.request_id}</dd>
                    </div>
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Created</dt>
                        <dd className="mt-1 text-sm text-gray-900">{new Date(request.created_at).toLocaleString()}</dd>
                    </div>
                    {request.completed_at && (
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Completed</dt>
                            <dd className="mt-1 text-sm text-gray-900">{new Date(request.completed_at).toLocaleString()}</dd>
                        </div>
                    )}
                    {request.error_message && (
                        <div className="col-span-2">
                            <dt className="text-sm font-medium text-red-500">Error</dt>
                            <dd className="mt-1 text-sm text-red-700">{request.error_message}</dd>
                        </div>
                    )}
                </dl>
            </div>

            {/* Search Results */}
            <div className="bg-white shadow rounded-lg p-6 mb-6">
                <h3 className="text-xl font-bold mb-4">Search Results ({search_results.length})</h3>
                {search_results.length === 0 ? (
                    <p className="text-gray-500">No search results yet.</p>
                ) : (
                    <div className="space-y-4">
                        {search_results.map((result) => (
                            <div key={result.id} className="border border-gray-200 rounded-lg p-4">
                                <h4 className="font-semibold text-lg mb-2">
                                    <a href={result.url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-800">
                                        {result.title}
                                    </a>
                                </h4>
                                <p className="text-sm text-gray-500 mb-2">{result.url}</p>
                                <div className="text-sm text-gray-700 bg-gray-50 p-3 rounded max-h-40 overflow-y-auto">
                                    {result.content ? (
                                        <p>{result.content.substring(0, 500)}{result.content.length > 500 ? '...' : ''}</p>
                                    ) : (
                                        <p className="text-gray-400 italic">No content extracted</p>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* AI Analysis */}
            {analysis_result && (
                <div className="bg-white shadow rounded-lg p-6">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-xl font-bold">AI Summary</h3>
                        <span className="text-sm text-gray-500">
                            Inference time: {analysis_result.inference_time_ms}ms
                        </span>
                    </div>
                    <div className="prose max-w-none bg-gray-50 p-4 rounded-lg whitespace-pre-wrap">
                        {analysis_result.summary}
                    </div>
                </div>
            )}

            {!analysis_result && request.status !== 'failed' && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <p className="text-yellow-800">
                        {request.status === 'completed' ? 'No analysis result available.' : 'Analysis in progress...'}
                    </p>
                </div>
            )}
        </div>
    );
}

export default RequestDetail;
