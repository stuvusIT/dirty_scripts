SET @oldsite='http://stuvus.uni-stuttgart.de'; 
SET @newsite='https://test.stuvus.uni-stuttgart.de';
UPDATE wp_options SET option_value = replace(option_value, @oldsite, @newsite) WHERE option_name = 'home' OR option_name = 'siteurl';
UPDATE wp_posts SET post_content = replace(post_content, @oldsite, @newsite);
UPDATE wp_links SET link_url = replace(link_url, @oldsite, @newsite);
UPDATE wp_postmeta SET meta_value = replace(meta_value, @oldsite, @newsite);



UPDATE wp_comments SET comment_content = REPLACE (comment_content, @oldsite, @newsite);
UPDATE wp_comments SET comment_author_url = REPLACE (comment_author_url, @oldsite, @newsite);
UPDATE wp_posts SET guid = REPLACE (guid, @oldsite, @newsite) WHERE post_type = 'attachment';


