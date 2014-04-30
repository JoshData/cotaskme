function show_modal_error(title, message) {
	$('#error_modal h4').text(title);
	$('#error_modal p').text(message);
	$('#error_modal').modal({});
}

var confirm_modal_callback = null;
function show_modal_confirm(title, message, callback) {
  confirm_modal_callback = callback;
  $('#confirm_modal h4').text(title);
  $('#confirm_modal p').text(message);
  $("#confirm_modal .btn-danger").off("click").click(callback);
  $('#confirm_modal').modal({});
}

function post_task_typehead_init(form) {
  form.find('#' + form.attr('id') + "-recipient").typeahead({
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
}

var nav_post_err_title = "Post Task";

function post_state(form_id, state) {
	var elems = $('#' + form_id).find('input, #nav_post_form select, #nav_post_form textarea, #nav_post_form button');
	elems.prop("disabled", !state);
}

var anonymous_claim_id = null;
function do_post_task(form, view_orientation, callback) {
  var form_id = $(form).attr('id');

  var elem_title = $('#' + form_id + '-title');
  var elem_recipient = $('#' + form_id + '-recipient');
  var elem_assigner = $('#' + form_id + '-assigner');
  var elem_assigner_email = $('#' + form_id + '-assigner-email');

	if (elem_title.val() == "") {
  		show_modal_error(nav_post_err_title, "Provide a title for the task.");
  		return false;
	}

  if (elem_recipient.val() == "") {
      show_modal_error(nav_post_err_title, "Type who you want to assign this task to.");
      return false;
  }

	$.ajax(
		"/_post",
		{
			data: {
        view_orientation: view_orientation, /* "incoming" or "outgoing" depending on what sort of list we are currently viewing, which controls how the task is rendered */
				title: elem_title.val(),
				notes: "",
				incoming: elem_recipient.val(),
        outgoing: elem_assigner.length ? elem_assigner.val() : elem_recipient.val(),
        assigner_email: elem_assigner_email.val(),
        claim_id: anonymous_claim_id
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

        // hold our new anonymous_claim_id in case we submit more tasks
        anonymous_claim_id = res.anonymous_claim_id;
        window.location.hash = "#claim=" + anonymous_claim_id;

        // call the callback!
        callback(res);
			},
			error: function() {
		  	show_modal_error(nav_post_err_title, "There was an error, sorry.");
		  	post_state(true);
			}
		});
	return false;
}

function start_login(a_elem) {
  // Where should the login page redirect to? Back to this page.
  var next = window.location;

  // If we put a claim UUID in the hash, modify the login target page
  // to stop first at a view that will claim anonymous tasks. Then
  // return to this URL.
  if (window.location.hash.substr(0, 7) == "#claim=")
    next = "/_claim?id=" + window.location.hash.substr(7) + "&next=" + encodeURIComponent(next);

  // Okay, redirect to login with the next paramater storing where we want to go after.
  window.location = a_elem.href + "?next=" + encodeURIComponent(next);
  return false; // prevent default link behavior
}