function show_modal_error(title, message) {
	$('#error_modal h4').text(title);
	$('#error_modal p').text(message);
	$('#error_modal').modal({});
}

$(function() {
  $('#navPostIncoming').typeahead({
    autoselect: true,
    highlight: true,
  }, {
    name: 'source',
    templates: {
      suggestion: function(item) {
        return $('<div/>').text(item.label).html();
      }
    },
    source: function(query, cb) {
      $.ajax(
        "/_search_for_recipient",
        {
          data: { query: query },
          method: "POST",
          success: function(res) { cb(res); },
          error: function() {
            cb([]);
          }
        });
    }
  });
});

var nav_post_err_title = "Post Task";

function post_state(form_id, state) {
	var elems = $('#' + form_id).find('input, #nav_post_form select, #nav_post_form textarea, #nav_post_form button');
	elems.prop("disabled", !state);
}

function do_post_task(form, callback) {
  var form_id = $(form).attr('id');

  var elem_title = $('#' + form_id + '-title');
  var elem_recipient = $('#' + form_id + '-recipient');
  var elem_assigner = $('#' + form_id + '-assigner');

	if (elem_title.val() == "") {
  		show_modal_error(nav_post_err_title, "Provide a title for the task.");
  		return false;
	}

	$.ajax(
		"/_post",
		{
			data: {
				title: elem_title.val(),
				notes: "",
				incoming: elem_recipient.val(),
				outgoing: elem_assigner.length ? elem_assigner.val() : elem_recipient.val()
			},
			method: "POST",
			success: function(res) {
		  	post_state(true);
				if (res.status != "ok") {
					show_modal_error(nav_post_err_title, res.msg);
					return;
				}

  			// reset fields to prevent double-submit
  			elem_title.val('');

        callback(res);
			},
			error: function() {
		  	show_modal_error(nav_post_err_title, "There was an error, sorry.");
		  	post_state(true);
			}
		});
	return false;
}