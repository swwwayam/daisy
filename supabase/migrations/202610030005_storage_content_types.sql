-- Runtime storage includes exact source CSVs and JSON DataFrame snapshots.
-- Keep MIME restrictions aligned with the backend's explicit upload headers.
update storage.buckets
  set public=false, file_size_limit=52428800,
      allowed_mime_types=array['text/csv','application/json']
  where id='datasets';
update storage.buckets
  set public=false, file_size_limit=52428800,
      allowed_mime_types=array['application/zip']
  where id='model-artifacts';
