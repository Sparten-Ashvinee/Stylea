package com.stylea.app.ui.activities

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import coil.load
import com.stylea.app.R
import com.stylea.app.databinding.ActivityMainBinding
import com.stylea.app.ui.viewmodels.TryOnViewModel
import java.io.File

/**
 * Main entry screen.
 *
 * Allows the user to:
 *  - Pick a fashion image from the gallery
 *  - Pick their own photo from the gallery or take a selfie
 *  - Launch the try-on flow
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val viewModel: TryOnViewModel by viewModels()

    // Temp file used for camera capture
    private var cameraImageFile: File? = null

    // -----------------------------------------------------------------------
    // Activity result launchers
    // -----------------------------------------------------------------------

    private val pickFashionLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? -> uri?.let { viewModel.setFashionUri(it) } }

    private val pickPersonLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? -> uri?.let { viewModel.setPersonUri(it) } }

    private val cameraLauncher = registerForActivityResult(
        ActivityResultContracts.TakePicture()
    ) { success ->
        if (success) {
            cameraImageFile?.let { file ->
                val uri = FileProvider.getUriForFile(
                    this,
                    "${packageName}.fileprovider",
                    file,
                )
                viewModel.setPersonUri(uri)
            }
        }
    }

    private val cameraPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) launchCamera() else showPermissionDeniedToast()
    }

    private val storagePermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) pickPersonLauncher.launch("image/*") else showPermissionDeniedToast()
    }

    // -----------------------------------------------------------------------
    // Lifecycle
    // -----------------------------------------------------------------------

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupClickListeners()
        observeViewModel()
    }

    // -----------------------------------------------------------------------
    // Setup
    // -----------------------------------------------------------------------

    private fun setupClickListeners() {
        binding.cardFashion.setOnClickListener { pickFashionLauncher.launch("image/*") }
        binding.btnPickFashion.setOnClickListener { pickFashionLauncher.launch("image/*") }

        binding.cardPerson.setOnClickListener { showPersonImageOptions() }
        binding.btnPickPerson.setOnClickListener { requestStorageAndPickPerson() }
        binding.btnTakeSelfie.setOnClickListener { requestCameraAndLaunch() }

        binding.btnTryOn.setOnClickListener { viewModel.startTryOn() }
    }

    private fun observeViewModel() {
        viewModel.fashionUri.observe(this) { uri ->
            if (uri != null) {
                binding.llFashionPlaceholder.visibility = View.GONE
                coilLoad(binding.ivFashion, uri)
            } else {
                binding.llFashionPlaceholder.visibility = View.VISIBLE
            }
        }

        viewModel.personUri.observe(this) { uri ->
            if (uri != null) {
                binding.llPersonPlaceholder.visibility = View.GONE
                coilLoad(binding.ivPerson, uri)
            } else {
                binding.llPersonPlaceholder.visibility = View.VISIBLE
            }
        }

        viewModel.uiState.observe(this) { state ->
            when (state) {
                is TryOnViewModel.UiState.Idle -> setLoading(false)
                is TryOnViewModel.UiState.SegmentingClothing -> {
                    setLoading(true, getString(R.string.loading_segmenting))
                }
                is TryOnViewModel.UiState.GeneratingTryOn -> {
                    setLoading(true, getString(R.string.loading_tryon))
                }
                is TryOnViewModel.UiState.Success -> {
                    setLoading(false)
                    TryOnActivity.result = state.result
                    navigateToTryOnResult()
                }
                is TryOnViewModel.UiState.Error -> {
                    setLoading(false)
                    Toast.makeText(this, state.message, Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    // -----------------------------------------------------------------------
    // Navigation
    // -----------------------------------------------------------------------

    private fun navigateToTryOnResult() {
        startActivity(Intent(this, TryOnActivity::class.java))
    }

    // -----------------------------------------------------------------------
    // UI helpers
    // -----------------------------------------------------------------------

    private fun setLoading(loading: Boolean, statusText: String? = null) {
        val visibility = if (loading) View.VISIBLE else View.GONE
        binding.progressBar.visibility = visibility
        binding.tvStatus.visibility = visibility
        binding.tvStatus.text = statusText
        binding.btnTryOn.isEnabled = !loading
        binding.btnPickFashion.isEnabled = !loading
        binding.btnPickPerson.isEnabled = !loading
        binding.btnTakeSelfie.isEnabled = !loading
    }

    private fun coilLoad(imageView: android.widget.ImageView, uri: Uri) {
        imageView.load(uri) {
            crossfade(true)
            placeholder(android.R.drawable.ic_menu_gallery)
        }
    }

    // -----------------------------------------------------------------------
    // Person image source chooser
    // -----------------------------------------------------------------------

    private fun showPersonImageOptions() {
        val options = arrayOf(
            getString(R.string.btn_pick_photo),
            getString(R.string.btn_take_selfie),
        )
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.label_your_photo))
            .setItems(options) { _, which ->
                when (which) {
                    0 -> requestStorageAndPickPerson()
                    1 -> requestCameraAndLaunch()
                }
            }
            .show()
    }

    // -----------------------------------------------------------------------
    // Camera & storage permission handling
    // -----------------------------------------------------------------------

    private fun requestCameraAndLaunch() {
        when {
            ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                    == PackageManager.PERMISSION_GRANTED -> launchCamera()
            shouldShowRequestPermissionRationale(Manifest.permission.CAMERA) ->
                showRationale(Manifest.permission.CAMERA, cameraPermissionLauncher)
            else -> cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun requestStorageAndPickPerson() {
        val permission = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
            Manifest.permission.READ_MEDIA_IMAGES
        else
            Manifest.permission.READ_EXTERNAL_STORAGE

        when {
            ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED ->
                pickPersonLauncher.launch("image/*")
            shouldShowRequestPermissionRationale(permission) ->
                showRationale(permission, storagePermissionLauncher)
            else -> storagePermissionLauncher.launch(permission)
        }
    }

    private fun launchCamera() {
        val cacheDir = File(cacheDir, "camera_images").also { it.mkdirs() }
        val file = File.createTempFile("selfie_", ".jpg", cacheDir)
        cameraImageFile = file
        val uri = FileProvider.getUriForFile(this, "${packageName}.fileprovider", file)
        cameraLauncher.launch(uri)
    }

    private fun showRationale(
        permission: String,
        launcher: androidx.activity.result.ActivityResultLauncher<String>,
    ) {
        AlertDialog.Builder(this)
            .setMessage("Permission is required to access this feature.")
            .setPositiveButton("Grant") { _, _ -> launcher.launch(permission) }
            .setNegativeButton("Deny", null)
            .show()
    }

    private fun showPermissionDeniedToast() {
        Toast.makeText(this, "Permission denied.", Toast.LENGTH_SHORT).show()
    }
}
