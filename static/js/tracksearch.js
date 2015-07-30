
function search_track()
{
	var artist_name = $('#artist-name').val();
	var track_name = $('#track-name').val();

	if (artist_name.length == 0) {
		$('#alert-artist-missing').show();
		return false;
	}
	else {
		$('#alert-artist-missing').hide();
	}

	$('#search-results').html('Loading...');

	$.ajax({
		type: 'POST',
		url: window.location.protocol + '//' + window.location.host + '/recs/trackname/',
		async: true,
		timeout: 10000,
		dataType: 'json',
		data: JSON.stringify({artist_name: artist_name, track_name: track_name}),
		success: function(data) {
			if (data.status != 'ok') {
				$('#search-results').html('Oops, an error occurred.');
			}
			else {
				update_search_results(data.search_results);
			}
		},
		error: function(data) {
			$('#search-results').html('Oops, an error occurred.');
		}
	});

	return false; //prevent form submission
}

function update_search_results(tracks)
{
	var html = [];
	var i = 0;

	html[i++] = '<table class="table table-condensed table-hover">';
	html[i++] = '<thead>';
	html[i++] = '<tr>';
	html[i++] = '<th>Track Id</th>';
	html[i++] = '<th>Track Name</th>';
	html[i++] = '<th>Artist Name</th>';
	html[i++] = '<th>Artist Id</th>';
	html[i++] = '</tr>';
	html[i++] = '</thead>';
	html[i++] = '<tbody>';

	$.each(tracks, function(index, track) {
		html[i++] = '<tr class="clickable-row" id="' + track.id + '" onclick="on_track_selected(this);">';
		html[i++] = '<td>' + track.id + '</td>';
		html[i++] = '<td>' + track.name + '</td>';
		html[i++] = '<td>' + track.artist_name + '</td>';
		html[i++] = '<td>' + track.artist_id + '</td>';
		html[i++] = '</tr>';

	});

	html[i++] = '</tbody>';
	html[i++] = '</table>';

	$('#search-results').html(html.join('')); 
}

function on_track_selected(row)
{
	$('.modal-title').html('Track id: ' + row.id);
	load_track_info(row.id);
	$('#modal-track_select').modal('show');
}

function load_track_info(track_id)
{
	$('#modal-track-info').html('Loading track info...');

	$.ajax({
		type: 'POST',
		url: window.location.protocol + '//' + window.location.host + '/recs/trackinfo/',
		async: true,
		timeout: 10000,
		dataType: 'json',
		data: JSON.stringify({track_id: track_id}),
		success: function(data) {
			console.log(data);
			if (data.status != 'ok') {
				$('#modal-track-info').html('Oops, an error occurred.');
			}
			else {
				update_track_info(data.track_info);
			}
		},
		error: function(data) {
			$('#modal-track-info').html('Oops, an error occurred.');
		}
	});

}

function update_track_info(track)
{
	var html = [];
	var i = 0;

	html[i++] = '<p><strong>Track name: </strong>' + track.name + '</p>';
	html[i++] = '<p><strong>Artist name: </strong>' + track.artist_name + '</p>';
	html[i++] = '<p><strong>Artist id: </strong>' + track.artist_id + '</p>';
	html[i++] = '<p><strong>Album: </strong>' + track.album + '</p>';
	html[i++] = '<table class="table table-condensed table-striped">';
	html[i++] = '<thead>';
	html[i++] = '<tr>';
	html[i++] = '<th>Type</th>';
	html[i++] = '<th>Id</th>';
	html[i++] = '<th>Weight</th>';
	html[i++] = '<th>Name</th>';
	html[i++] = '</tr>';
	html[i++] = '</thead>';
	html[i++] = '<tbody>';

	$.each(track.descriptors, function(index, descriptor) {
		html[i++] = '<tr>';
		html[i++] = '<td>' + descriptor.type + '</td>';
		html[i++] = '<td>' + descriptor.id + '</td>';
		html[i++] = '<td>' + descriptor.weight + '</td>';
		html[i++] = '<td>' + descriptor.name + '</td>';
		html[i++] = '</tr>'; 
	});

	html[i++] = '</tbody>';
	html[i++] = '</table>';

	$('#modal-track-info').html(html.join(''));
}
